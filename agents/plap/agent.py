"""
PLAP Agent — Plan Agent Protocol.

Answers the question: "What does this plan allow?"

This is the authoritative source for plan-level data. FAP and PAAP both
query PLAP before making any compliance or execution decision.
"""

from agents.plap.models import PlanRecord
from data.db import get_plan


class PlanNotFound(Exception):
    pass


def query_plan(plan_id: str) -> PlanRecord:
    """Return full plan record. Raises PlanNotFound if plan does not exist."""
    plan = get_plan(plan_id)
    if plan is None:
        raise PlanNotFound(f"Plan '{plan_id}' not found.")
    return plan


def query_capabilities(plan_id: str) -> dict:
    """
    Return capability manifest — which transaction types this plan supports.
    Used by PAAP before accepting any write request.
    """
    plan = query_plan(plan_id)
    return {
        "plan_id":                    plan_id,
        "capabilities": {
            "loan_initiation":          plan.loan_policy.loans_permitted,
            "hardship_distribution":    plan.hardship_policy.hardship_permitted,
            "in_service_distribution":  plan.distribution_options.in_service_age_59_5,
            "separation_distribution":  True,   # always available on termination
            "investment_reallocation":  True,   # always available
            "deferral_change":          True,   # always available
            "rmd":                      True,   # always available when required
            "beneficiary_update":       True,   # always available
            "qdro":                     True,   # always available
            "direct_rollover_out":      plan.rollover_qdro.direct_rollover_out_permitted,
            "rollover_in":              plan.rollover_qdro.accepts_rollover_in,
        },
    }


def query_vesting(plan_id: str) -> dict:
    """Return vesting schedule and service crediting rules."""
    plan = query_plan(plan_id)
    s = plan.match_vesting_schedule
    return {
        "plan_id":                  plan_id,
        "vesting_type":             s.vesting_type.value,
        "cliff_years":              s.cliff_years,
        "graduated_schedule":       [
            {"year": b.year, "pct": b.pct}
            for b in (s.graduated_schedule or [])
        ],
        "service_crediting_method": s.service_crediting_method,
        "immediate_vesting_employee_contributions": True,  # ERISA §203 — always
    }


def query_fund_lineup(plan_id: str) -> dict:
    """Return investment fund lineup with QDIA flag."""
    plan = query_plan(plan_id)
    return {
        "plan_id": plan_id,
        "funds": [
            {
                "fund_id":       f.fund_id,
                "fund_name":     f.fund_name,
                "ticker":        f.ticker,
                "asset_class":   f.asset_class,
                "expense_ratio": f.expense_ratio,
                "is_qdia":       f.is_qdia,
            }
            for f in plan.fund_lineup
        ],
    }


def query_blackout_status(plan_id: str) -> dict:
    """Return current blackout period status."""
    plan = query_plan(plan_id)
    b = plan.blackout_status
    return {
        "plan_id":    plan_id,
        "is_active":  b.is_active,
        "start_date": b.start_date,
        "end_date":   b.end_date,
        "reason":     b.reason,
    }
