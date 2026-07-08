"""
Meta / lookup endpoints — no auth required.
Used by the UI to build login screens and dropdowns.

GET /meta/participants   — list all participants with display info
GET /meta/plans         — list all plans
GET /meta/actions       — list all valid action types with descriptions
"""

from fastapi import APIRouter
from data.participants import ALL_PARTICIPANTS
from data.plans import ALL_PLANS

router = APIRouter()


@router.get("/participants")
def list_participants():
    result = []
    for pid, p in ALL_PARTICIPANTS.items():
        result.append({
            "participant_id":   p.participant_id,
            "plan_id":          p.plan_id,
            "employment_status": p.employment_status.value,
            "years_of_service": p.years_of_vesting_service,
            "vesting_pct":      p.vesting_percentage,
            "loan_headroom":    float(p.max_additional_loan_amount),
            "outstanding_loans": len(p.outstanding_loans),
            "is_hce":           p.is_hce,
            "catch_up_eligible": p.age_50_or_older,
        })
    return {"count": len(result), "participants": result}


@router.get("/plans")
def list_plans():
    result = []
    for pid, plan in ALL_PLANS.items():
        result.append({
            "plan_id":         plan.plan_id,
            "plan_name":       plan.plan_name,
            "plan_type":       plan.plan_type.value,
            "blackout_active": plan.blackout_active,
            "loan_feature":    plan.loan_feature,
            "hardship_feature": plan.hardship_feature,
        })
    return {"count": len(result), "plans": result}


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
