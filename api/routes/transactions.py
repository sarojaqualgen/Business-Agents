"""
Supervised transaction endpoints — for confirm / cancel flows.

After a supervised action (loan, deferral to 0%) the crew returns
"supervised_pending". The UI shows a confirmation panel, then calls:

GET  /transactions/pending   — is there a supervised transaction waiting?
POST /transactions/confirm   — execute it
POST /transactions/cancel    — discard it
"""

import json

from fastapi import APIRouter, Depends, HTTPException

from api.auth import SessionToken, get_session
from crew.tools.paap_tools import (
    ExecuteTransactionTool,
    clear_supervised_pending,
    get_supervised_pending,
)

router = APIRouter()


def _participant_only(session: SessionToken) -> None:
    if session.principal_type not in ("participant", "participant_delegate"):
        raise HTTPException(403, "Only participants can confirm transactions")


@router.get("/pending")
def get_pending(session: SessionToken = Depends(get_session)):
    """
    Returns the supervised transaction waiting for confirmation, or null.
    UI should poll this after a /chat response that contained autonomy_level=supervised.
    """
    _participant_only(session)
    pending = get_supervised_pending(session.participant_id)
    if not pending:
        return {"has_pending": False, "pending": None}

    action = pending["action"]
    payload = pending["payload"]

    # Build a human-readable summary for the UI confirmation panel
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

    return {
        "has_pending":   True,
        "participant_id": session.participant_id,
        "action":        action,
        "action_label":  action.replace("_", " ").title(),
        "payload":       payload,
        "summary":       summary,
        "message":       "FAP approved this transaction. All 12 ERISA rules passed. Your explicit confirmation is required.",
    }


@router.post("/confirm")
def confirm_transaction(session: SessionToken = Depends(get_session)):
    """
    Execute the pending supervised transaction.
    Consumes the FAP token — cannot be reversed after this call.
    """
    _participant_only(session)
    pending = get_supervised_pending(session.participant_id)
    if not pending:
        raise HTTPException(404, "No pending transaction found for this participant")

    clear_supervised_pending(session.participant_id)

    tool = ExecuteTransactionTool()
    raw = tool._run(
        participant_id=session.participant_id,
        action=pending["action"],
        payload_json=pending["payload_json"],
        fap_token=pending["fap_token"],
        autonomy_level="full",   # force execution — participant already confirmed
    )

    try:
        result = json.loads(raw)
    except Exception:
        result = {"status": "unknown", "raw": raw}

    if "error" in result:
        raise HTTPException(400, result["error"])

    return result


@router.post("/cancel")
def cancel_transaction(session: SessionToken = Depends(get_session)):
    """
    Discard the pending supervised transaction. FAP token is abandoned (never consumed).
    """
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
