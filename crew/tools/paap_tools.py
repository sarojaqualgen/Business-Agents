"""
PAAP CrewAI tools — wraps the Participant Data Module for use by CrewAI agents.

PII minimization strictly enforced — the LLM never sees:
  - date_of_birth (FAP resolves age internally, returns boolean flags only)
  - ssn_hash
  - marital status (FAP handles QJSA internally)
  - full vested_balance (use GetLoanHeadroom for loan decisions)
"""

import json
from decimal import Decimal
from pydantic import BaseModel, Field
from crewai.tools import BaseTool

from data.participants import get_participant
from crew.tool_logger import record

# Re-exported from api.pending so the CrewAI CLI path keeps working.
from api.pending import (  # noqa: E402
    _supervised_pending,
    get_supervised_pending,
    set_supervised_pending,
    clear_supervised_pending,
)


class GetParticipantSummaryInput(BaseModel):
    participant_id: str = Field(description="Participant ID, e.g. PART-001")


class GetParticipantSummaryTool(BaseTool):
    name: str = "GetParticipantSummary"
    description: str = (
        "Retrieve a safe, PII-minimized summary of a participant's account status. "
        "Returns employment status, service years, deferral election, loan count, and eligibility flags. "
        "Does NOT return date of birth, SSN, marital status, or full account balance — "
        "use GetLoanHeadroom for loan capacity."
    )
    args_schema: type[BaseModel] = GetParticipantSummaryInput

    def _run(self, participant_id: str) -> str:
        p = get_participant(participant_id)
        if not p:
            record("GetParticipantSummary", participant_id, "ERROR: not found")
            return json.dumps({"error": f"Participant {participant_id} not found."})

        out = json.dumps({
            "participant_id": p.participant_id,
            "plan_id": p.plan_id,
            "employment_status": p.employment_status.value,
            "years_of_vesting_service": p.years_of_vesting_service,
            "vesting_percentage": p.vesting_percentage,
            "current_deferral_pct": p.current_deferral_pct,
            "deferral_type": p.deferral_type.value,
            "outstanding_loan_count": len(p.outstanding_loans),
            "prior_hardship_count": len(p.prior_hardship_distributions),
            "rmd_required": p.rmd_required,
            "is_hce": p.is_hce,
            "catch_up_eligible_50plus": p.age_50_or_older,
            "catch_up_eligible_60_63": p.age_60_to_63,
            "employee_contributions_ytd": float(p.employee_contributions_ytd),
            "employer_contributions_ytd": float(p.employer_contributions_ytd),
            "investment_elections": [
                {"fund_id": e.fund_id, "allocation_pct": e.allocation_pct}
                for e in p.investment_elections
            ],
        }, indent=2)
        record("GetParticipantSummary", participant_id,
               f"status={p.employment_status.value}  vesting={p.vesting_percentage:.0%}  loans={len(p.outstanding_loans)}")
        return out


class GetLoanHeadroomInput(BaseModel):
    participant_id: str = Field(description="Participant ID to calculate IRC § 72(p) loan capacity for")


class GetLoanHeadroomTool(BaseTool):
    name: str = "GetLoanHeadroom"
    description: str = (
        "Calculate the maximum loan amount this participant is eligible to borrow "
        "under IRC § 72(p): the lesser of $50,000 (minus highest prior balance in last 12 months) "
        "or 50% of vested balance. Use this to answer 'how much can I borrow?'."
    )
    args_schema: type[BaseModel] = GetLoanHeadroomInput

    def _run(self, participant_id: str) -> str:
        p = get_participant(participant_id)
        if not p:
            record("GetLoanHeadroom", participant_id, "ERROR: not found")
            return json.dumps({"error": f"Participant {participant_id} not found."})

        headroom = float(p.max_additional_loan_amount)
        out = json.dumps({
            "participant_id": participant_id,
            "loan_headroom_usd": headroom,
            "outstanding_loans": len(p.outstanding_loans),
            "note": "This is the max eligible per IRC § 72(p). Final approval requires FAP compliance check.",
        }, indent=2)
        record("GetLoanHeadroom", participant_id, f"headroom=${headroom:,.0f}")
        return out


class ExecuteTransactionInput(BaseModel):
    participant_id: str = Field(description="Participant ID for whom the transaction is being executed")
    action: str = Field(description="ActionType string, e.g. loan_initiation, deferral_change")
    payload_json: str = Field(description="JSON string with action-specific parameters, e.g. {\"amount\": 10000}")
    fap_token: str = Field(description="Valid FAP JWT token returned from RunComplianceCheck")
    autonomy_level: str = Field(description="Autonomy level from FAP: full, supervised, or human_review")


class ExecuteTransactionTool(BaseTool):
    name: str = "ExecuteTransaction"
    description: str = (
        "Execute an approved participant transaction using a valid FAP token. "
        "- full: executes immediately. "
        "- supervised: executes after participant confirmation (confirm before calling this). "
        "- human_review: does NOT execute — routes to plan sponsor approval queue. "
        "Always pass the exact payload that was submitted to RunComplianceCheck."
    )
    args_schema: type[BaseModel] = ExecuteTransactionInput

    def _run(
        self,
        participant_id: str,
        action: str,
        payload_json: str,
        fap_token: str,
        autonomy_level: str,
    ) -> str:
        import json as _json
        from agents.fap.tokens import validate_token
        from data.review_queue import enqueue
        from data.participants import get_participant as _get_participant

        try:
            payload = _json.loads(payload_json)
        except _json.JSONDecodeError:
            return _json.dumps({"error": "payload_json is not valid JSON."})

        if autonomy_level == "human_review":
            p = _get_participant(participant_id)
            entry_id = enqueue(
                participant_id=participant_id,
                plan_id=p.plan_id if p else "UNKNOWN",
                agent_id="system",
                principal_type="participant",
                action=action,
                payload=payload,
                fap_audit_id="",
                fap_token=fap_token,
                created_at="2026-07-02T00:00:00Z",
            )
            record("ExecuteTransaction", f"{participant_id}  {action}",
                   f"QUEUED for sponsor review  entry_id={entry_id}")
            return _json.dumps({
                "status": "queued_for_human_review",
                "queue_entry_id": entry_id,
                "message": (
                    f"Action '{action}' requires plan sponsor approval (ERISA fiduciary oversight). "
                    f"Entry ID {entry_id} added to review queue. "
                    "Participant will be notified when resolved."
                ),
            }, indent=2)

        if autonomy_level == "supervised":
            # Token is NOT consumed here — the CLI will confirm and execute separately.
            _supervised_pending[participant_id] = {
                "action": action,
                "payload": payload,
                "payload_json": payload_json,
                "fap_token": fap_token,
            }
            record("ExecuteTransaction", f"{participant_id}  {action}",
                   "SUPERVISED_PENDING  awaiting confirmation")
            return _json.dumps({
                "status": "supervised_pending",
                "participant_id": participant_id,
                "action": action,
                "payload": payload,
                "message": (
                    "Transaction requires participant confirmation before execution. "
                    "Do NOT call ExecuteTransaction again — the CLI will present the confirmation prompt."
                ),
            }, indent=2)

        # Validate and single-use-consume the FAP token
        valid, reason = validate_token(
            token_str=fap_token,
            expected_action=action,
            expected_participant_id=participant_id,
            expected_payload=payload,
        )
        if not valid:
            record("ExecuteTransaction", f"{participant_id}  {action}", f"ERROR: {reason}")
            return _json.dumps({"error": f"FAP token validation failed: {reason}"})

        record("ExecuteTransaction", f"{participant_id}  {action}",
               f"EXECUTED  autonomy={autonomy_level}")

        # Apply session-level overrides so the CLI immediately reflects the change
        # without a DB write (Phase 6 pending).
        # Wrapped in try/except: if the override fails after token was consumed,
        # un-consume the token so the participant can retry without re-initiating.
        try:
            if action == "investment_reallocation":
                from data.participants import apply_investment_override
                from agents.paap.models import InvestmentElection as _IE
                new_elections = [
                    _IE(fund_id=e["fund_id"], allocation_pct=float(e["allocation_pct"]))
                    for e in payload.get("elections", [])
                ]
                if new_elections:
                    apply_investment_override(participant_id, new_elections)
                    try:
                        from data.db import update_investment_elections, get_participant as _db_p
                        _p = _db_p(participant_id)
                        if _p:
                            update_investment_elections(
                                participant_id, _p.plan_id,
                                [{"fund_id": e.fund_id, "allocation_pct": e.allocation_pct} for e in new_elections],
                            )
                    except Exception:
                        pass  # in-memory override already applied; DB write is best-effort

            if action == "deferral_change" and "new_deferral_pct" in payload:
                from data.participants import apply_deferral_override
                new_pct = float(payload["new_deferral_pct"])
                d_type = payload.get("deferral_type", "pre_tax")
                apply_deferral_override(participant_id, new_pct, deferral_type=d_type)
                try:
                    from data.db import update_deferral
                    update_deferral(participant_id, new_pct, d_type)
                except Exception:
                    pass  # in-memory override already applied; DB write is best-effort

        except Exception as exc:
            # Rollback: un-consume the token so the participant can retry
            from agents.fap.tokens import unconsume_token
            unconsume_token(fap_token)
            record("ExecuteTransaction", f"{participant_id}  {action}",
                   f"ROLLBACK  token restored  reason={exc}")
            return _json.dumps({"error": f"Execution failed and was rolled back: {exc}. Your token has been restored — retry is safe."})

        return _json.dumps({
            "status": "executed",
            "participant_id": participant_id,
            "action": action,
            "payload": payload,
            "autonomy_level": autonomy_level,
            "message": (
                f"Transaction '{action}' successfully recorded for participant {participant_id}. "
                "Production: PAAP applies this to the ledger via recordkeeper write path."
            ),
        }, indent=2)
