"""
Plan data layer — reads from PostgreSQL via data.db.
PLAN-003: Capital One Financial Corporation Associate Savings Plan
PLAN-004: The Prudential Employee Savings Plan (PESP)
"""

from data.db import all_plan_ids, get_capabilities, get_plan
from agents.plap.models import PlanRecord, PlanCapabilities

def get_plan_ids() -> list[str]:
    return all_plan_ids()
