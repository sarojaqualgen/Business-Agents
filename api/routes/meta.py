"""
Meta / lookup endpoints — no auth required.
Used by the UI to build login screens and dropdowns.

GET /meta/participants   — list all participants with display info
GET /meta/plans         — list all plans
GET /meta/actions       — list all valid action types with descriptions
"""

from fastapi import APIRouter, Depends, HTTPException
from api.auth import SessionToken, get_session

router = APIRouter()


@router.get("/participants")
def list_participants():
    from data.db import all_participant_ids
    from data.participants import get_participant
    result = []
    for pid in all_participant_ids():
        p = get_participant(pid)
        if not p:
            continue
        result.append({
            "participant_id":    p.participant_id,
            "plan_id":           p.plan_id,
            "display_name":      getattr(p, "display_name", None) or p.participant_id,
            "employment_status": p.employment_status.value,
            "years_of_service":  p.years_of_vesting_service,
            "vesting_pct":       p.vesting_percentage,
            "loan_headroom":     float(p.max_additional_loan_amount),
            "outstanding_loans": len(p.outstanding_loans),
            "is_hce":            p.is_hce,
            "catch_up_eligible": p.age_50_or_older,
        })
    return {"count": len(result), "participants": result}


@router.get("/plans")
def list_plans():
    from data.db import all_plan_ids
    from data.plans import get_plan
    result = []
    for pid in all_plan_ids():
        plan = get_plan(pid)
        if not plan:
            continue
        result.append({
            "plan_id":            plan.plan_id,
            "plan_name":          plan.plan_name,
            "plan_type":          plan.plan_type.value,
            "blackout_active":    plan.blackout_status.is_active,
            "loans_permitted":    plan.loan_policy.loans_permitted,
            "hardship_permitted": plan.hardship_policy.hardship_permitted,
        })
    return {"count": len(result), "plans": result}


@router.get("/participant/activity")
def participant_activity(session: SessionToken = Depends(get_session)):
    """
    Unified activity history for the logged-in participant.
    Returns executed transactions (from DB), FAP denials, and review queue entries,
    all merged into a single list sorted newest-first.
    """
    participant_id = session.participant_id
    if not participant_id:
        return {"participant_id": None, "activities": []}

    activities: list[dict] = []

    # 1. Executed transactions from DB
    executed_tx_ids: set[str] = set()
    try:
        from data import db
        for tx in db.get_participant_transactions(participant_id):
            executed_tx_ids.add(tx["id"])
            activities.append({
                "id":        tx["id"],
                "type":      "executed",
                "action":    tx["action"],
                "amount":    tx["amount"],
                "timestamp": tx["timestamp"],
                "label":     None,
                "note":      None,
            })
    except Exception:
        pass

    # 1b. Loan records from participant_loans (catches pre-seeded / recordkeeper loans
    #     that were never routed through the transactions table).
    try:
        from data import db as _db
        txn_loan_dates = {
            a["timestamp"][:10] for a in activities
            if a["action"] == "loan_initiation" and a["timestamp"]
        }
        for loan in _db.get_participant_loans(participant_id):
            loan_date = (loan["timestamp"] or "")[:10]
            # Skip if a transaction already covers this date (system-originated loan)
            if loan_date and loan_date in txn_loan_dates:
                continue
            activities.append({
                "id":        loan["id"],
                "type":      "loan",
                "action":    "loan_initiation",
                "amount":    loan["amount"],
                "timestamp": loan["timestamp"],
                "label":     "Active Loan" if loan["status"] == "active" else loan["status"].title(),
                "note":      loan["note"],
                "outstanding": loan["outstanding"],
                "loan_status": loan["status"],
            })
    except Exception:
        pass

    # 2. FAP denials from in-memory audit log
    try:
        from agents.fap.agent import get_all_audit_records
        for r in get_all_audit_records():
            if r.participant_id != participant_id or r.authorized:
                continue
            activities.append({
                "id":        r.audit_id,
                "type":      "denied",
                "action":    r.action,
                "amount":    None,
                "timestamp": r.timestamp,
                "label":     None,
                "note":      getattr(r, "denial_reason", None),
                "denial_code": getattr(r, "denial_code", None),
            })
    except Exception:
        pass

    # 3. Review queue entries for this participant
    try:
        from data.review_queue import get_all as rq_get_all
        for e in rq_get_all():
            if e.participant_id != participant_id:
                continue
            status = e.status
            if status == "pending":
                act_type = "pending_review"
            elif status == "approved_awaiting_bank_details":
                act_type = "awaiting_bank"
            else:
                act_type = status  # approved, denied
            activities.append({
                "id":        e.entry_id,
                "type":      act_type,
                "action":    e.action,
                "amount":    e.payload.get("amount") if e.payload else None,
                "timestamp": e.created_at if hasattr(e, "created_at") else None,
                "label":     None,
                "note":      f"Status: {status}",
                "entry_id":  e.entry_id,
            })
    except Exception:
        pass

    # Sort newest-first (None timestamps go last)
    activities.sort(
        key=lambda a: a["timestamp"] or "0000",
        reverse=True,
    )

    return {"participant_id": participant_id, "activities": activities}


@router.get("/actions")
def list_actions():
    return {
        "actions": [
            {
                "action":       "loan_initiation",
                "label":        "Loan",
                "autonomy":     "supervised",
                "description":  "Borrow from your vested balance. Max = lesser of $50k or 50% vested.",
                "example":      "I want to take a loan of $10,000 for 5 years",
            },
            {
                "action":       "deferral_change",
                "label":        "Change Deferral %",
                "autonomy":     "full or supervised",
                "description":  "Change what % of each paycheck goes to your 401(k).",
                "example":      "Change my deferral to 8%",
            },
            {
                "action":       "investment_reallocation",
                "label":        "Rebalance Investments",
                "autonomy":     "full",
                "description":  "Change how your money is invested across the fund lineup.",
                "example":      "Put 60% in FIDELITY-500 and 40% in VANGUARD-TDF-2040",
            },
            {
                "action":       "address_update",
                "label":        "Update Address",
                "autonomy":     "full",
                "description":  "Update mailing address. No ERISA compliance rules — fastest action.",
                "example":      "Update my address to 123 Main St, Chicago IL 60601",
            },
            {
                "action":       "hardship_distribution",
                "label":        "Hardship Withdrawal",
                "autonomy":     "human_review",
                "description":  "Withdraw for immediate financial need. Subject to tax + 10% penalty. Sponsor must approve.",
                "example":      "I need a hardship withdrawal of $5,000 for medical emergency",
            },
            {
                "action":       "beneficiary_update",
                "label":        "Update Beneficiary",
                "autonomy":     "human_review",
                "description":  "Change who receives your account if you pass away.",
                "example":      "Change my beneficiary to my spouse",
            },
            {
                "action":       "qdro",
                "label":        "QDRO",
                "autonomy":     "human_review",
                "description":  "Split account per court order in a divorce. Requires 5 legal fields.",
                "example":      "QDRO — Participant: John Doe, Alternate payee: Jane Doe, Plan: Capital One 401k, Amount: 50% vested balance, Payment period: lump sum",
            },
            {
                "action":       "in_service_distribution",
                "label":        "In-Service Distribution",
                "autonomy":     "human_review",
                "description":  "Withdraw while still employed. Only available at age 59½+.",
                "example":      "I want to take an in-service distribution",
            },
        ]
    }


@router.get("/participant/investments")
def get_participant_investments(session: SessionToken = Depends(get_session)):
    """
    Returns the plan's fund lineup and the participant's current investment elections.
    Used by the Investments reallocation UI.
    """
    if session.principal_type not in ("participant", "participant_delegate"):
        raise HTTPException(403, "Only participants can view investment elections")

    from data.participants import get_participant
    participant = get_participant(session.participant_id)
    if not participant:
        raise HTTPException(404, "Participant not found")

    from data.plans import get_plan
    plan = get_plan(participant.plan_id)
    if not plan:
        raise HTTPException(404, "Plan not found")

    election_map = {e.fund_id: e.allocation_pct for e in participant.investment_elections}

    return {
        "participant_id": participant.participant_id,
        "plan_id":        participant.plan_id,
        "blackout_active": plan.blackout_status.is_active,
        "current_elections": [
            {"fund_id": e.fund_id, "allocation_pct": e.allocation_pct}
            for e in participant.investment_elections
        ],
        "fund_lineup": [
            {
                "fund_id":       f.fund_id,
                "fund_name":     f.fund_name,
                "ticker":        f.ticker,
                "asset_class":   f.asset_class,
                "expense_ratio": f.expense_ratio,
                "is_qdia":       f.is_qdia,
                "current_pct":   election_map.get(f.fund_id, 0.0),
            }
            for f in plan.fund_lineup
        ],
    }


@router.get("/participant/deferral")
def get_participant_deferral(session: SessionToken = Depends(get_session)):
    """
    Returns current deferral info for the logged-in participant.
    Used by the Contribution Change UI.
    """
    if session.principal_type not in ("participant", "participant_delegate"):
        raise HTTPException(403, "Only participants can view deferral info")

    from data.participants import get_participant
    participant = get_participant(session.participant_id)
    if not participant:
        raise HTTPException(404, "Participant not found")

    from data.plans import get_plan
    plan = get_plan(participant.plan_id)
    if not plan:
        raise HTTPException(404, "Plan not found")

    return {
        "participant_id":       participant.participant_id,
        "current_deferral_pct": float(participant.current_deferral_pct),
        "deferral_type":        participant.deferral_type.value,
        "catch_up_eligible":    participant.age_50_or_older,
        "is_hce":               participant.is_hce,
        "blackout_active":      plan.blackout_status.is_active,
        "annual_compensation":  float(participant.compensation_ytd),
    }
