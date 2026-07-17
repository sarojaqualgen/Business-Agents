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
from agents.paap.agent import (
    execute as paap_execute,
    execute_confirmed,
    get_participant_plan_id,
    ParticipantNotFound,
    PlanDoesNotSupportAction,
    UnauthorizedByFAP,
)
from crew.tools.paap_tools import (
    ExecuteTransactionTool,
    clear_supervised_pending,
    get_supervised_pending,
    set_supervised_pending,
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

    # Non-disbursement supervised action (e.g. deferral to 0%) — execute now via PAAP
    clear_supervised_pending(session.participant_id)
    try:
        result = execute_confirmed(
            participant_id=session.participant_id,
            action=action,
            payload=pending["payload"],
            fap_token=pending["fap_token"],
        )
    except UnauthorizedByFAP as e:
        raise HTTPException(400, f"Token validation failed: {e.denial_reason}")
    except ParticipantNotFound as e:
        raise HTTPException(404, str(e))
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

        try:
            result = execute_confirmed(
                participant_id=session.participant_id,
                action=entry.action,
                payload=entry.payload,
                fap_token=entry.fap_token,
            )
        except UnauthorizedByFAP as e:
            raise HTTPException(400, f"Token validation failed: {e.denial_reason}")
        except ParticipantNotFound as e:
            raise HTTPException(404, str(e))

        # Mark queue entry done only after PAAP execution succeeded
        finalize_disbursed(body.entry_id)

    else:
        # ── Supervised disbursement ────────────────────────────────────
        pending = _get_disbursement_pending(session.participant_id)
        if not pending:
            raise HTTPException(
                404,
                "No transaction awaiting disbursement. "
                "Call POST /transactions/confirm first."
            )

        try:
            result = execute_confirmed(
                participant_id=session.participant_id,
                action=pending["action"],
                payload=pending["payload"],
                fap_token=pending["fap_token"],
            )
        except UnauthorizedByFAP as e:
            raise HTTPException(400, f"Token validation failed: {e.denial_reason}")
        except ParticipantNotFound as e:
            raise HTTPException(404, str(e))

        # Clear pending only after PAAP execution succeeded
        _clear_disbursement_pending(session.participant_id)

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
    UI-driven investment reallocation. Routes through PAAP → PLAP → FAP → execute.
    Always returns full autonomy for this action type.
    """
    _participant_only(session)

    from agents.plap.agent import query_fund_lineup

    # Validate fund IDs are in the plan lineup — ask PLAP, not DB directly
    try:
        plan_id = get_participant_plan_id(session.participant_id)
    except ParticipantNotFound as e:
        raise HTTPException(404, str(e))

    fund_data = query_fund_lineup(plan_id)
    valid_fund_ids = {f["fund_id"] for f in fund_data.get("funds", [])}
    for e in body.elections:
        if e.fund_id not in valid_fund_ids:
            raise HTTPException(400, f"Fund '{e.fund_id}' is not in this plan's lineup")

    elections_payload = [{"fund_id": e.fund_id, "allocation_pct": e.allocation_pct} for e in body.elections]
    payload = {"scope": body.scope, "elections": elections_payload}

    try:
        paap_execute(
            participant_id=session.participant_id,
            agent_id=session.agent_id or "portal",
            action="investment_reallocation",
            payload=payload,
        )
    except ParticipantNotFound as e:
        raise HTTPException(404, str(e))
    except UnauthorizedByFAP as e:
        raise HTTPException(400, f"FAP denied: {e.denial_reason}")

    return {
        "status":    "executed",
        "action":    "investment_reallocation",
        "scope":     body.scope,
        "elections": elections_payload,
        "message":   "Investment elections updated successfully.",
    }


# ── POST /transactions/change-deferral ────────────────────────────────────────

class ChangeDeferralRequest(BaseModel):
    new_deferral_pct: float  # 0.0–1.0
    deferral_type: Literal["pre_tax", "roth"] = "pre_tax"
    catch_up: bool = False

    @field_validator("new_deferral_pct")
    @classmethod
    def pct_in_range(cls, v: float) -> float:
        if not (0.0 <= v <= 1.0):
            raise ValueError("new_deferral_pct must be between 0.0 and 1.0")
        return v


@router.post("/change-deferral")
def change_deferral(body: ChangeDeferralRequest, session: SessionToken = Depends(get_session)):
    """
    UI-driven deferral rate change. Routes through PAAP → PLAP → FAP → execute.

    - Full autonomy (pct > 0): PAAP executes immediately, returns status='executed'.
    - Supervised autonomy (pct == 0): PAAP returns fap_token, caller stores it,
      returns status='requires_confirmation'. UI must then call POST /transactions/confirm.
    """
    _participant_only(session)

    payload = {
        "new_deferral_pct": body.new_deferral_pct,
        "deferral_type":    body.deferral_type,
        "catch_up":         body.catch_up,
    }

    try:
        result = paap_execute(
            participant_id=session.participant_id,
            agent_id=session.agent_id or "portal",
            action="deferral_change",
            payload=payload,
        )
    except ParticipantNotFound as e:
        raise HTTPException(404, str(e))
    except UnauthorizedByFAP as e:
        raise HTTPException(400, f"FAP denied: {e.denial_reason}")

    # deferral to 0% → supervised — PAAP did not execute, returns fap_token
    if result["autonomy_level"] == "supervised" and result.get("fap_token"):
        set_supervised_pending(
            session.participant_id,
            action="deferral_change",
            payload=payload,
            payload_json=json.dumps(payload),
            fap_token=result["fap_token"],
        )
        return {
            "status":  "requires_confirmation",
            "action":  "deferral_change",
            "payload": payload,
            "warning": "Setting to 0% will stop all retirement contributions. Please confirm.",
        }

    return {
        "status":           "executed",
        "action":           "deferral_change",
        "new_deferral_pct": body.new_deferral_pct,
        "deferral_type":    body.deferral_type,
        "message":          f"Deferral rate updated to {body.new_deferral_pct * 100:.1f}% ({body.deferral_type.replace('_', '-')}).",
    }
