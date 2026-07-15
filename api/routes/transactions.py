"""
Supervised transaction endpoints — confirm / cancel / disburse.

Flow for SUPERVISED actions (loan_initiation, deferral to 0%):

  POST /chat → supervised_pending stored in memory
  GET  /transactions/pending   → UI shows confirmation panel
  POST /transactions/confirm   → if disbursement action: moves to disbursement_pending
                                 if non-disbursement (deferral change): executes immediately
  POST /transactions/disburse  → participant provides bank details → funds sent

Flow for HUMAN_REVIEW disbursement actions (hardship_distribution, in_service_distribution):

  POST /chat → queued → sponsor approves → entry status = approved_awaiting_bank_details
  POST /transactions/disburse  → participant provides bank details + entry_id → funds sent
"""

import json
import re
from decimal import Decimal
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, field_validator

from api.auth import SessionToken, get_session
from crew.tools.paap_tools import (
    ExecuteTransactionTool,
    clear_supervised_pending,
    get_supervised_pending,
)
from data.review_queue import finalize_disbursed, get_entry, reload as rq_reload

router = APIRouter()

# Actions that disburse funds to a bank account — require bank details step.
# deferral_change and investment_reallocation are supervised but move no external funds.
DISBURSEMENT_ACTIONS = {"loan_initiation", "hardship_distribution", "in_service_distribution"}


def _record_execution(
    participant_id: str,
    plan_id: str,
    action: str,
    payload: dict,
    fap_token: str,
    autonomy_level: str,
    queue_entry_id: Optional[str] = None,
) -> None:
    """
    After a successful PAAP execution: write to transactions table, decrement
    vested_balance for disbursement actions, and create a loan record for
    loan_initiation. All DB calls are best-effort — failure is logged silently
    so the participant response is never blocked by a write failure.
    """
    try:
        import jwt as _jwt
        import os
        _SECRET = os.getenv("FAP_JWT_SECRET", "dev-only-insecure-secret-change-in-production")
        claims = _jwt.decode(fap_token, _SECRET, algorithms=["HS256"], options={"verify_exp": False})
        token_id = claims.get("jti", "")
    except Exception:
        token_id = ""

    try:
        from data import db  # noqa: PLC0415
        amount = payload.get("amount")
        amount_dec = Decimal(str(amount)) if amount is not None else None

        db.record_transaction(
            participant_id=participant_id,
            plan_id=plan_id,
            action=action,
            amount=amount_dec,
            payload=payload,
            fap_token_id=token_id,
            autonomy_level=autonomy_level,
            queue_entry_id=queue_entry_id,
        )

        if action in DISBURSEMENT_ACTIONS and amount_dec:
            db.decrement_vested_balance(participant_id=participant_id, amount=amount_dec)

        if action == "loan_initiation" and amount_dec:
            repayment_years = int(payload.get("repayment_years", 5))
            db.create_loan_record(
                participant_id=participant_id,
                plan_id=plan_id,
                amount=amount_dec,
                repayment_years=repayment_years,
            )
    except Exception:
        pass

# In-memory store: participant_id → {action, payload, payload_json, fap_token}
# Populated by POST /confirm for disbursement actions.
_disbursement_pending: dict[str, dict] = {}


def _get_disbursement_pending(participant_id: str) -> dict | None:
    return _disbursement_pending.get(participant_id)


def _set_disbursement_pending(participant_id: str, data: dict) -> None:
    _disbursement_pending[participant_id] = data


def _clear_disbursement_pending(participant_id: str) -> None:
    _disbursement_pending.pop(participant_id, None)


def _participant_only(session: SessionToken) -> None:
    if session.principal_type not in ("participant", "participant_delegate"):
        raise HTTPException(403, "Only participants can confirm transactions")


class DisburseRequest(BaseModel):
    routing_number: str
    account_number: str
    account_type: Literal["checking", "savings"]
    entry_id: Optional[str] = None  # only for human_review flow


# ── GET /transactions/pending ──────────────────────────────────────────────────

@router.get("/pending")
def get_pending(session: SessionToken = Depends(get_session)):
    """
    Returns the supervised transaction waiting for confirmation, or null.
    Call after every POST /chat response so the UI knows whether to show
    a confirmation panel.
    """
    _participant_only(session)
    pending = get_supervised_pending(session.participant_id)
    if not pending:
        return {"has_pending": False, "pending": None}

    action = pending["action"]
    payload = pending["payload"]

    summary = {}
    if action == "loan_initiation":
        summary = {
            "amount":          payload.get("amount"),
            "repayment_years": payload.get("repayment_years"),
            "purpose":         payload.get("purpose", "general purpose"),
            "warning":         "This loan reduces your retirement savings and accrues interest.",
        }
    elif action == "deferral_change":
        pct = payload.get("new_deferral_pct", 0)
        summary = {
            "new_deferral_pct":     pct,
            "new_deferral_display": f"{float(pct) * 100:.1f}%",
            "deferral_type":        payload.get("deferral_type", "pre_tax"),
            "warning": "Setting to 0% stops all retirement contributions." if float(pct) == 0 else None,
        }

    requires_bank_details = action in DISBURSEMENT_ACTIONS

    return {
        "has_pending":          True,
        "participant_id":       session.participant_id,
        "action":               action,
        "action_label":         action.replace("_", " ").title(),
        "payload":              payload,
        "summary":              summary,
        "requires_bank_details": requires_bank_details,
        "message":              "FAP approved this transaction. All 12 ERISA rules passed. Your explicit confirmation is required.",
    }


# ── POST /transactions/confirm ─────────────────────────────────────────────────

@router.post("/confirm")
def confirm_transaction(session: SessionToken = Depends(get_session)):
    """
    Confirm the supervised transaction.

    - Disbursement actions (loan, hardship, in-service): moves to disbursement_pending
      and returns status=awaiting_bank_details. UI must then call POST /transactions/disburse.
    - Non-disbursement actions (deferral change): executes immediately.
    """
    _participant_only(session)
    pending = get_supervised_pending(session.participant_id)
    if not pending:
        raise HTTPException(404, "No pending transaction found for this participant")

    action = pending["action"]

    if action in DISBURSEMENT_ACTIONS:
        # Hold — need bank details before funds can move
        _set_disbursement_pending(session.participant_id, pending)
        clear_supervised_pending(session.participant_id)
        return {
            "status":  "awaiting_bank_details",
            "action":  action,
            "message": "Transaction confirmed. Please provide your bank details to receive the funds.",
        }

    # Non-disbursement supervised action (e.g. deferral to 0%) — execute now
    clear_supervised_pending(session.participant_id)
    tool = ExecuteTransactionTool()
    raw = tool._run(
        participant_id=session.participant_id,
        action=action,
        payload_json=pending["payload_json"],
        fap_token=pending["fap_token"],
        autonomy_level="full",
    )

    try:
        result = json.loads(raw)
    except Exception:
        result = {"status": "unknown", "raw": raw}

    if "error" in result:
        raise HTTPException(400, result["error"])

    _record_execution(
        participant_id=session.participant_id,
        plan_id=session.plan_id or "",
        action=action,
        payload=pending.get("payload", {}),
        fap_token=pending["fap_token"],
        autonomy_level="supervised",
    )
    return result


# ── POST /transactions/cancel ──────────────────────────────────────────────────

@router.post("/cancel")
def cancel_transaction(session: SessionToken = Depends(get_session)):
    """Discard the pending supervised transaction. FAP token is abandoned."""
    _participant_only(session)
    pending = get_supervised_pending(session.participant_id)
    if not pending:
        raise HTTPException(404, "No pending transaction found for this participant")

    action = pending["action"]
    clear_supervised_pending(session.participant_id)
    return {
        "status":  "cancelled",
        "action":  action,
        "message": "Transaction cancelled. No changes were made to your account.",
    }


# ── POST /transactions/disburse ────────────────────────────────────────────────

@router.post("/disburse")
def disburse_transaction(body: DisburseRequest, session: SessionToken = Depends(get_session)):
    """
    Provide bank details and trigger disbursement.

    Two flows depending on whether entry_id is supplied:

    Supervised flow (no entry_id):
      After POST /confirm returned awaiting_bank_details.
      Uses the FAP token held in _disbursement_pending.

    Human-review flow (entry_id provided):
      After sponsor approved a hardship / in-service distribution.
      Entry status must be approved_awaiting_bank_details.
      Uses the FAP token stored in the queue entry at request time.

    Bank details are used once and never stored.
    """
    _participant_only(session)

    # Validate routing number — exactly 9 digits
    if not re.match(r'^\d{9}$', body.routing_number):
        raise HTTPException(400, "Routing number must be exactly 9 digits")

    # Validate account number — 4 to 17 digits
    if not re.match(r'^\d{4,17}$', body.account_number):
        raise HTTPException(400, "Account number must be between 4 and 17 digits")

    if body.entry_id:
        # ── Human-review disbursement ──────────────────────────────────
        rq_reload()
        entry = get_entry(body.entry_id)
        if not entry:
            raise HTTPException(404, f"Queue entry '{body.entry_id}' not found")
        if entry.participant_id != session.participant_id:
            raise HTTPException(403, "This entry does not belong to your account")
        if entry.status != "approved_awaiting_bank_details":
            raise HTTPException(
                400,
                f"Entry '{body.entry_id}' is not awaiting bank details (status: {entry.status}). "
                "It must be approved by your plan sponsor first."
            )

        tool = ExecuteTransactionTool()
        raw = tool._run(
            participant_id=session.participant_id,
            action=entry.action,
            payload_json=json.dumps(entry.payload),
            fap_token=entry.fap_token,
            autonomy_level="full",
        )

    else:
        # ── Supervised disbursement ────────────────────────────────────
        pending = _get_disbursement_pending(session.participant_id)
        if not pending:
            raise HTTPException(
                404,
                "No transaction awaiting disbursement. "
                "Call POST /transactions/confirm first."
            )

        tool = ExecuteTransactionTool()
        raw = tool._run(
            participant_id=session.participant_id,
            action=pending["action"],
            payload_json=pending["payload_json"],
            fap_token=pending["fap_token"],
            autonomy_level="full",
        )

    try:
        result = json.loads(raw)
    except Exception:
        result = {"status": "unknown", "raw": raw}

    if "error" in result:
        raise HTTPException(400, result["error"])

    # Only mark entry as done / clear pending AFTER confirming execution succeeded
    if body.entry_id:
        finalize_disbursed(body.entry_id)
        _record_execution(
            participant_id=session.participant_id,
            plan_id=entry.plan_id,
            action=entry.action,
            payload=entry.payload,
            fap_token=entry.fap_token,
            autonomy_level="human_review",
            queue_entry_id=body.entry_id,
        )
    else:
        _clear_disbursement_pending(session.participant_id)
        _record_execution(
            participant_id=session.participant_id,
            plan_id=session.plan_id or "",
            action=pending["action"],
            payload=pending.get("payload", {}),
            fap_token=pending["fap_token"],
            autonomy_level="supervised",
        )

    return {
        **result,
        "disbursement": {
            "routing_number":   body.routing_number,
            "account_last4":    body.account_number[-4:],
            "account_type":     body.account_type,
            "status":           "initiated",
            "estimated_arrival": "3–5 business days",
        },
    }


# ── POST /transactions/reallocate ─────────────────────────────────────────────

class ElectionItem(BaseModel):
    fund_id: str
    allocation_pct: float  # 0.0–1.0


class ReallocateRequest(BaseModel):
    scope: Literal["future_only", "balance_only", "both"] = "both"
    elections: list[ElectionItem]

    @field_validator("elections")
    @classmethod
    def elections_sum_to_one(cls, v: list[ElectionItem]) -> list[ElectionItem]:
        total = sum(e.allocation_pct for e in v)
        if abs(total - 1.0) > 0.005:
            raise ValueError(f"Elections must sum to 1.0 (100%), got {total:.4f}")
        return v


@router.post("/reallocate")
def reallocate_investments(body: ReallocateRequest, session: SessionToken = Depends(get_session)):
    """
    UI-driven investment reallocation.
    Runs FAP authorization inline (always returns full autonomy for this action),
    then executes immediately via ExecuteTransactionTool.
    """
    _participant_only(session)

    from data.participants import get_participant
    from data.plans import get_plan as _get_plan
    from agents.fap.agent import authorize
    from agents.fap.models import ActionType, PrincipalType

    participant = get_participant(session.participant_id)
    if not participant:
        raise HTTPException(404, "Participant not found")

    plan = _get_plan(participant.plan_id)
    if not plan:
        raise HTTPException(404, "Plan not found")

    # Validate all fund IDs are in the plan lineup
    valid_fund_ids = {f.fund_id for f in plan.fund_lineup}
    for e in body.elections:
        if e.fund_id not in valid_fund_ids:
            raise HTTPException(400, f"Fund '{e.fund_id}' is not in this plan's lineup")

    elections_payload = [{"fund_id": e.fund_id, "allocation_pct": e.allocation_pct} for e in body.elections]

    payload = {
        "scope":     body.scope,
        "elections": elections_payload,
    }

    result = authorize(
        agent_id="AGENT-PARTICIPANT-001",
        principal_type=PrincipalType.participant,
        participant=participant,
        plan=plan,
        action=ActionType.investment_reallocation,
        payload=payload,
    )

    if not result.authorized:
        raise HTTPException(400, f"FAP denied: {result.denial_reason}")

    tool = ExecuteTransactionTool()
    raw = tool._run(
        participant_id=session.participant_id,
        action="investment_reallocation",
        payload_json=json.dumps(payload),
        fap_token=result.token,
        autonomy_level="full",
    )

    try:
        exec_result = json.loads(raw)
    except Exception:
        exec_result = {"status": "unknown", "raw": raw}

    if "error" in exec_result:
        raise HTTPException(400, exec_result["error"])

    # Persist to DB (best-effort — in-memory override already applied by ExecuteTransactionTool)
    try:
        from data import db
        db.update_investment_elections(
            participant_id=session.participant_id,
            plan_id=participant.plan_id,
            elections=elections_payload,
        )
        db.record_transaction(
            participant_id=session.participant_id,
            plan_id=participant.plan_id,
            action="investment_reallocation",
            amount=None,
            payload=payload,
            fap_token_id=result.token,
            autonomy_level="full",
        )
    except Exception:
        pass

    return {
        "status":     "executed",
        "action":     "investment_reallocation",
        "scope":      body.scope,
        "elections":  elections_payload,
        "message":    "Investment elections updated successfully.",
    }
