"""
PLAP CrewAI tools — wraps the Plan Rules Module for use by CrewAI agents.
Only plan-level (non-PII) data is returned. No participant data here.
"""

import json
from pydantic import BaseModel, Field
from crewai.tools import BaseTool

from data.plans import get_plan
from crew.tool_logger import record


class GetPlanRulesInput(BaseModel):
    plan_id: str = Field(description="Plan ID to fetch rules for, e.g. PLAN-001")


class GetPlanRulesTool(BaseTool):
    name: str = "GetPlanRules"
    description: str = (
        "Retrieve the compliance rules and policies for a specific plan. "
        "Returns loan policy, hardship policy, vesting schedule, eligibility requirements, "
        "and blackout status. Call this before any participant action to know what the plan allows."
    )
    args_schema: type[BaseModel] = GetPlanRulesInput

    def _run(self, plan_id: str) -> str:
        plan = get_plan(plan_id)
        if not plan:
            record("GetPlanRules", plan_id, "ERROR: not found")
            return json.dumps({"error": f"Plan {plan_id} not found."})

        out = json.dumps({
            "plan_id": plan.plan_id,
            "plan_name": plan.plan_name,
            "plan_type": plan.plan_type,
            "safe_harbor": plan.safe_harbor,
            "blackout_active": plan.blackout_status.is_active,
            "blackout_start": plan.blackout_status.start_date,
            "blackout_end": plan.blackout_status.end_date,
            "blackout_reason": plan.blackout_status.reason,
            "eligibility_age": plan.eligibility_age,
            "eligibility_months_of_service": plan.eligibility_months_of_service,
            "loans_permitted": plan.loan_policy.loans_permitted,
            "max_loan_amount": plan.loan_policy.max_loan_amount,
            "max_loan_pct_of_vested": plan.loan_policy.max_loan_pct_of_vested,
            "min_loan_amount": plan.loan_policy.min_loan_amount,
            "max_outstanding_loans": plan.loan_policy.outstanding_loans_permitted,
            "max_repayment_years": plan.loan_policy.max_repayment_years,
            "hardship_permitted": plan.hardship_policy.hardship_permitted,
            "hardship_standard": plan.hardship_policy.hardship_standard,
            "qualifying_hardship_expenses": [e.value for e in plan.hardship_policy.qualifying_expenses],
            "in_service_age_59_5": plan.distribution_options.in_service_age_59_5,
            "rmd_start_rule": plan.distribution_options.rmd_start_rule,
            "vesting_type": plan.match_vesting_schedule.vesting_type,
            "cliff_years": plan.match_vesting_schedule.cliff_years,
            "accepts_rollover_in": plan.rollover_qdro.accepts_rollover_in,
        }, indent=2)
        record("GetPlanRules", plan_id,
               f"loans={plan.loan_policy.loans_permitted}  blackout={plan.blackout_status.is_active}  hardship={plan.hardship_policy.hardship_permitted}")
        return out


class GetFundLineupInput(BaseModel):
    plan_id: str = Field(description="Plan ID to fetch fund lineup for")


class GetFundLineupTool(BaseTool):
    name: str = "GetFundLineup"
    description: str = (
        "Retrieve the investment fund lineup available in a specific plan. "
        "Returns fund names, tickers, asset classes, expense ratios, and QDIA flag. "
        "Use this when a participant or advisor asks about investment options."
    )
    args_schema: type[BaseModel] = GetFundLineupInput

    def _run(self, plan_id: str) -> str:
        plan = get_plan(plan_id)
        if not plan:
            record("GetFundLineup", plan_id, "ERROR: not found")
            return json.dumps({"error": f"Plan {plan_id} not found."})

        funds = [
            {
                "fund_id": f.fund_id,
                "fund_name": f.fund_name,
                "ticker": f.ticker,
                "asset_class": f.asset_class,
                "expense_ratio_pct": round(f.expense_ratio * 100, 3),
                "is_qdia": f.is_qdia,
            }
            for f in plan.fund_lineup
        ]
        out = json.dumps({"plan_id": plan_id, "fund_count": len(funds), "funds": funds}, indent=2)
        record("GetFundLineup", plan_id, f"{len(funds)} funds")
        return out
