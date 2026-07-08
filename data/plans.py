"""
Plan data layer — reads from PostgreSQL via data.db.
PLAN-003: Capital One Financial Corporation Associate Savings Plan
PLAN-004: The Prudential Employee Savings Plan (PESP)
"""

from data.db import all_plan_ids, get_capabilities, get_plan
from agents.plap.models import PlanRecord, PlanCapabilities

ALL_PLANS: dict[str, PlanRecord] = {}
for _pid in all_plan_ids():
    _p = get_plan(_pid)
    if _p:
        ALL_PLANS[_pid] = _p

PLAN_003 = ALL_PLANS.get("PLAN-003")
PLAN_004 = ALL_PLANS.get("PLAN-004")
