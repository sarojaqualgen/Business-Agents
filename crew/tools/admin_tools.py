"""
Admin CrewAI tools — plan sponsor and trustee actions.

These tools handle administrative duties that do NOT route through FAP participant compliance:
  - Reviewing and approving/denying the human_review queue
  - Managing blackout periods (ERISA § 101(i) — 30-day advance notice required)
  - Viewing plan-level configuration

Plan sponsors cannot initiate participant transactions here — they can only approve or deny queued ones.
"""

import json
from pydantic import BaseModel, Field
from crewai.tools import BaseTool

from data.review_queue import get_pending, get_all, approve, deny, get_entry
from crew.tool_logger import record


# ---------------------------------------------------------------------------
# Human Review Queue Tools
# ---------------------------------------------------------------------------

class GetPendingReviewsInput(BaseModel):
    plan_id: str = Field(
        default="",
        description="Optional: filter by plan_id. Leave empty to see all pending items.",
    )


class GetPendingReviewsTool(BaseTool):
    name: str = "GetPendingReviews"
    description: str = (
        "Retrieve all transactions in the human review queue awaiting plan sponsor approval. "
        "These are actions where FAP approved the request but ERISA requires a fiduciary to authorize "
        "(hardship distributions, QDROs, beneficiary updates, RMDs, separation distributions). "
        "Use this to show the sponsor what needs their attention."
    )
    args_schema: type[BaseModel] = GetPendingReviewsInput

    def _run(self, plan_id: str = "") -> str:
        pending = get_pending()
        if plan_id:
            pending = [e for e in pending if e.plan_id == plan_id]

        if not pending:
            return json.dumps({
                "pending_count": 0,
                "message": "No items awaiting review.",
                "entries": [],
            }, indent=2)

        entries = [
            {
                "entry_id": e.entry_id,
                "participant_id": e.participant_id,
                "plan_id": e.plan_id,
                "action": e.action,
                "payload": e.payload,
                "created_at": e.created_at,
                "fap_audit_id": e.fap_audit_id,
            }
            for e in pending
        ]
        out = json.dumps({"pending_count": len(entries), "entries": entries}, indent=2)
        record("GetPendingReviews", plan_id or "all", f"{len(entries)} pending")
        return out


class ApproveRequestInput(BaseModel):
    entry_id: str = Field(description="Review queue entry ID to approve, e.g. A1B2C3D4")
    sponsor_note: str = Field(
        default="",
        description="Optional note from the plan sponsor explaining the approval decision",
    )


class ApproveRequestTool(BaseTool):
    name: str = "ApproveRequest"
    description: str = (
        "Approve a pending transaction in the human review queue. "
        "The participant's action will then be executed by PAAP. "
        "Include a sponsor_note for ERISA audit trail purposes."
    )
    args_schema: type[BaseModel] = ApproveRequestInput

    def _run(self, entry_id: str, sponsor_note: str = "") -> str:
        entry = approve(
            entry_id=entry_id,
            sponsor_note=sponsor_note,
            resolved_at="2026-07-02T00:00:00Z",
        )
        if not entry:
            record("ApproveRequest", entry_id, "ERROR: not found")
            return json.dumps({"error": f"Entry {entry_id} not found or not in pending status."})

        record("ApproveRequest", entry_id, f"APPROVED  {entry.action}  {entry.participant_id}")
        return json.dumps({
            "status": "approved",
            "entry_id": entry.entry_id,
            "participant_id": entry.participant_id,
            "action": entry.action,
            "payload": entry.payload,
            "sponsor_note": entry.sponsor_note,
            "message": (
                f"Action '{entry.action}' for participant {entry.participant_id} has been approved. "
                "PAAP will execute this transaction. "
                "Production: participant receives email notification; PAAP writes to ledger."
            ),
        }, indent=2)


class DenyRequestInput(BaseModel):
    entry_id: str = Field(description="Review queue entry ID to deny, e.g. A1B2C3D4")
    sponsor_note: str = Field(
        description="Required: reason for denial. This is recorded in the ERISA audit log.",
    )


class DenyRequestTool(BaseTool):
    name: str = "DenyRequest"
    description: str = (
        "Deny a pending transaction in the human review queue. "
        "Provide a clear reason in sponsor_note — it is recorded in the ERISA audit trail. "
        "The participant will be notified that their request was denied."
    )
    args_schema: type[BaseModel] = DenyRequestInput

    def _run(self, entry_id: str, sponsor_note: str = "") -> str:
        entry = deny(
            entry_id=entry_id,
            sponsor_note=sponsor_note,
            resolved_at="2026-07-02T00:00:00Z",
        )
        if not entry:
            record("DenyRequest", entry_id, "ERROR: not found")
            return json.dumps({"error": f"Entry {entry_id} not found or not in pending status."})

        record("DenyRequest", entry_id, f"DENIED  {entry.action}  {entry.participant_id}")
        return json.dumps({
            "status": "denied",
            "entry_id": entry.entry_id,
            "participant_id": entry.participant_id,
            "action": entry.action,
            "denial_reason": entry.sponsor_note,
            "message": (
                f"Action '{entry.action}' for participant {entry.participant_id} has been denied. "
                "Production: participant receives email notification with denial reason."
            ),
        }, indent=2)


# ---------------------------------------------------------------------------
# Blackout Management Tool
# ---------------------------------------------------------------------------

class ManageBlackoutInput(BaseModel):
    plan_id: str = Field(description="Plan ID to manage blackout for")
    operation: str = Field(
        description="'activate' to start a blackout, 'deactivate' to end one, 'status' to check current state"
    )
    start_date: str = Field(
        default="",
        description="Blackout start date (YYYY-MM-DD). Required for 'activate'. Must be ≥ 30 days from today per ERISA § 101(i).",
    )
    end_date: str = Field(
        default="",
        description="Blackout end date (YYYY-MM-DD). Required for 'activate'.",
    )
    reason: str = Field(
        default="",
        description="Reason for blackout (e.g. 'recordkeeper transition', 'fund lineup change'). Required for 'activate'.",
    )


class ManageBlackoutTool(BaseTool):
    name: str = "ManageBlackout"
    description: str = (
        "Manage blackout periods for a plan. "
        "ERISA § 101(i) requires 30-day advance written notice to participants before any blackout. "
        "Blackouts block all participant writes (loans, distributions, reallocations). "
        "Operations: 'activate', 'deactivate', 'status'."
    )
    args_schema: type[BaseModel] = ManageBlackoutInput

    def _run(
        self,
        plan_id: str,
        operation: str,
        start_date: str = "",
        end_date: str = "",
        reason: str = "",
    ) -> str:
        from data.plans import get_plan

        plan = get_plan(plan_id)
        if not plan:
            return json.dumps({"error": f"Plan {plan_id} not found."})

        if operation == "status":
            bs = plan.blackout_status
            return json.dumps({
                "plan_id": plan_id,
                "blackout_active": bs.is_active,
                "start_date": bs.start_date,
                "end_date": bs.end_date,
                "reason": bs.reason,
            }, indent=2)

        if operation == "activate":
            if not start_date or not end_date or not reason:
                return json.dumps({
                    "error": "start_date, end_date, and reason are required to activate a blackout.",
                    "erisa_note": "ERISA § 101(i) requires 30-day advance notice to all participants.",
                })
            # Production: validate 30-day notice window, update DB, send participant notices
            return json.dumps({
                "status": "blackout_activated",
                "plan_id": plan_id,
                "start_date": start_date,
                "end_date": end_date,
                "reason": reason,
                "notice_required_by": "30 days before start_date per ERISA § 101(i)",
                "message": (
                    "Production: blackout record updated in PostgreSQL; "
                    "participant notice emails queued for delivery. "
                    "All write operations will be blocked during this period."
                ),
            }, indent=2)

        if operation == "deactivate":
            return json.dumps({
                "status": "blackout_deactivated",
                "plan_id": plan_id,
                "message": "Blackout period ended. Participant write operations are now permitted.",
            }, indent=2)

        return json.dumps({"error": f"Unknown operation '{operation}'. Use: activate, deactivate, status."})
