"""
Admin endpoints — plan sponsors only.

GET  /admin/audit        — FAP audit log (all compliance decisions)
GET  /admin/blackout     — blackout status for a plan
POST /admin/blackout     — activate or lift a blackout (crew-routed)
"""

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional

from api.auth import SessionToken, get_session
from api.streaming import stream_crew
from agents.fap.agent import get_all_audit_records
from crew.router import route
import agents.fap.agent as _fap_agent
import data.review_queue as _rq

router = APIRouter()


def _sponsor_only(session: SessionToken) -> None:
    if session.principal_type not in ("plan_sponsor", "plan_trustee"):
        raise HTTPException(403, "Only plan sponsors can access admin endpoints")


@router.get("/audit")
def audit_log(session: SessionToken = Depends(get_session)):
    _sponsor_only(session)
    records = get_all_audit_records()
    return {
        "count": len(records),
        "note":  "Audit log stored in PostgreSQL fap_audit_log (falls back to in-memory if DB unavailable).",
        "records": [
            {
                "audit_id":           r.audit_id,
                "timestamp":          r.timestamp,
                "agent_id":           r.agent_id,
                "participant_id":     r.participant_id,
                "plan_id":            r.plan_id,
                "action":             r.action,
                "authorized":         r.authorized,
                "autonomy_level":     getattr(r, "autonomy_level", None),
                "denial_code":        getattr(r, "denial_code", None),
                "denial_reason":      getattr(r, "denial_reason", None),
                "erisa_citation":     getattr(r, "erisa_citation", None),
                "master_ref_section": getattr(r, "master_ref_section", None),
            }
            for r in records
        ],
    }


@router.post("/reset")
def reset_demo(session: SessionToken = Depends(get_session)):
    """
    Wipe all transient demo state so you can start fresh.
    Clears: FAP audit log, review queue, supervised-pending dict,
            document store, and the PostgreSQL transactions + fap_audit_log tables.
    Daniela Reyes' seeded loan (LOAN-0100) is preserved / restored.
    """
    _sponsor_only(session)
    report = {}

    # 1 — in-memory FAP audit log
    _fap_agent._audit_log.clear()
    report["fap_audit_log_memory"] = "cleared"

    # 2 — in-memory review queue
    _rq._queue.clear()
    report["review_queue_memory"] = "cleared"

    # 3 — supervised-pending, disbursement-pending, and in-memory consumed tokens
    from crew.tools.paap_tools import _supervised_pending
    _supervised_pending.clear()
    from api.routes.transactions import _disbursement_pending
    _disbursement_pending.clear()
    from agents.fap.tokens import _consumed_tokens
    _consumed_tokens.clear()
    report["supervised_pending"] = "cleared"
    report["disbursement_pending"] = "cleared"
    report["consumed_tokens_memory"] = "cleared"

    # 3b — in-memory investment + deferral overrides
    from data.participants import _election_overrides, _deferral_overrides
    _election_overrides.clear()
    _deferral_overrides.clear()
    report["participant_overrides_memory"] = "cleared"

    # 4 — document store (JSON file + in-memory cache)
    try:
        from data import document_store as _ds
        _ds._docs.clear()
        if _ds._STORE_FILE.exists():
            _ds._STORE_FILE.unlink()
        report["document_store"] = "cleared"
    except Exception as e:
        report["document_store"] = f"error: {e}"

    # 5 — JSON fallback files
    try:
        from data.review_queue import _QUEUE_FILE
        if _QUEUE_FILE.exists():
            _QUEUE_FILE.unlink()
        report["review_queue_json"] = "deleted"
    except Exception as e:
        report["review_queue_json"] = f"error: {e}"

    # 6 — PostgreSQL tables (CASCADE handles FK dependencies)
    try:
        from data.db import _conn
        with _conn() as conn:
            cur = conn.cursor()
            # Clear transient tables — CASCADE handles any FK edges
            cur.execute("TRUNCATE TABLE fap_tokens CASCADE")
            cur.execute("TRUNCATE TABLE transactions CASCADE")
            cur.execute("TRUNCATE TABLE fap_audit_log CASCADE")
            cur.execute("TRUNCATE TABLE review_queue CASCADE")

            # Remove any test loans, then restore Daniela's seeded loan
            cur.execute("TRUNCATE TABLE participant_loans CASCADE")
            cur.execute("""
                INSERT INTO participant_loans
                    (loan_id, participant_id, plan_id, loan_type,
                     original_amount, outstanding_balance, highest_balance_last_12_months,
                     interest_rate, origination_date, maturity_date,
                     payment_amount, payment_frequency, status)
                VALUES
                    ('LOAN-0100', 'PART-009', 'PLAN-003', 'general',
                     25000.00, 22000.00, 25000.00,
                     0.0850, '2024-05-01', '2029-05-01',
                     512.00, 'monthly', 'active')
                ON CONFLICT (loan_id) DO NOTHING
            """)

            # Restore all participant balances and deferral rates to seeded values
            seeded_participants = [
                ("PART-006", 225000.00, 210000.00, 0.10, "pre_tax"),
                ("PART-007",  42000.00,  38000.00, 0.04, "pre_tax"),
                ("PART-008",  92000.00,  85000.00, 0.06, "pre_tax"),
                ("PART-009", 105000.00, 100000.00, 0.08, "pre_tax"),
            ]
            for pid, total, vested, deferral, d_type in seeded_participants:
                cur.execute(
                    """UPDATE participants
                       SET total_balance = %s, vested_balance = %s,
                           current_deferral_pct = %s, deferral_type = %s
                       WHERE participant_id = %s""",
                    (total, vested, deferral, d_type, pid),
                )

            # Restore investment elections to seeded values
            cur.execute("TRUNCATE TABLE participant_investment_elections CASCADE")
            seeded_elections = [
                ("PART-006", "PLAN-003", "COF-LIFEPATH-2030", 0.60),
                ("PART-006", "PLAN-003", "COF-SP500",         0.25),
                ("PART-006", "PLAN-003", "COF-STABLE",        0.15),
                ("PART-007", "PLAN-004", "PESP-GOALMAKER-MOD", 1.00),
                ("PART-008", "PLAN-003", "COF-LIFEPATH-2040", 0.70),
                ("PART-008", "PLAN-003", "COF-SP500",         0.30),
                ("PART-009", "PLAN-003", "COF-SP500",         0.70),
                ("PART-009", "PLAN-003", "COF-STABLE",        0.30),
            ]
            for pid, plan_id, fund_id, pct in seeded_elections:
                cur.execute(
                    """INSERT INTO participant_investment_elections
                           (participant_id, plan_id, fund_id, allocation_pct, effective_date)
                       VALUES (%s, %s, %s, %s, '2024-01-01')""",
                    (pid, plan_id, fund_id, pct),
                )

        report["postgres"] = "truncated; balances, deferral rates, and elections restored; LOAN-0100 restored"
    except Exception as e:
        report["postgres"] = f"error: {e}"

    return {"status": "reset", "details": report}


class BlackoutRequest(BaseModel):
    message: str   # natural-language — routed through SponsorCrew


@router.post("/blackout")
async def manage_blackout(
    req: BlackoutRequest,
    session: SessionToken = Depends(get_session),
):
    _sponsor_only(session)
    crew = route(
        principal_type=session.principal_type,
        query=req.message,
        participant_id=session.participant_id or "",
        plan_id=session.plan_id or "",
        agent_id=session.agent_id,
    )
    return StreamingResponse(
        stream_crew(crew, session.principal_type),
        media_type="text/event-stream",
        headers={
            "Cache-Control":    "no-cache",
            "X-Accel-Buffering": "no",
            "Connection":       "keep-alive",
        },
    )
