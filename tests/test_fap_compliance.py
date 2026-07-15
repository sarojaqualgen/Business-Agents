"""
pytest tests for the FAP 12-rule ERISA compliance engine.

Plans used:
  PLAN-003  Capital One Associate Savings Plan  — eligibility_age=18, 2yr cliff, 10yr primary-res loan
  PLAN-004  Prudential PESP                     — eligibility_age=21, 3yr cliff

Participants:
  PART-008  Amara Osei     — Capital One, age 36, fully eligible, no loans  (primary fixture)
  PART-006  Gabriel Stone  — Capital One, age 61, HCE, over 59½              (near_retirement_participant)
  PART-007  Yuki Tanaka    — Prudential, 1.5yr service, cliff not yet met    (young_participant)
  PART-009  Daniela Reyes  — Capital One, has existing $25k loan             (loan_participant)

Run:
    pytest tests/test_fap_compliance.py -v
"""

import copy
from datetime import date
from decimal import Decimal

import pytest

from agents.fap.compliance import (
    run_compliance_check,
    rule_01_delegation_validity,
    rule_02_blackout_period,
    rule_03_participation_eligibility,
    rule_04_vesting_enforcement,
    rule_05_contribution_limits,
    rule_06_plan_rules,
    rule_07_early_withdrawal_penalty,
    rule_08_anti_alienation,
    rule_09_prohibited_transaction,
    rule_10_prudent_expert_loyalty,
    rule_11_rmd_failure_prevention,
    rule_12_autonomy_level,
)
from agents.fap.models import ActionType, AutonomyLevel, DenialCode, PrincipalType
from agents.plap.models import BlackoutStatus
from data.participants import get_participant as _get_p
from data.plans import get_plan as _get_plan

PART_006 = _get_p("PART-006")
PART_007 = _get_p("PART-007")
PART_008 = _get_p("PART-008")
PART_009 = _get_p("PART-009")
PLAN_003 = _get_plan("PLAN-003")
PLAN_004 = _get_plan("PLAN-004")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def participant():
    """PART-008 Amara Osei: age 36, Capital One, fully eligible, $85k vested, no loans."""
    return copy.deepcopy(PART_008)


@pytest.fixture
def plan():
    """PLAN-003 Capital One: immediate eligibility (age 18), 2yr cliff, loans permitted."""
    return copy.deepcopy(PLAN_003)


@pytest.fixture
def prudential_plan():
    """PLAN-004 Prudential PESP: 1yr wait, 3yr cliff, loans permitted."""
    return copy.deepcopy(PLAN_004)


@pytest.fixture
def blackout_plan(plan):
    """PLAN-003 copy with an active blackout — simulates recordkeeper transition."""
    p = copy.deepcopy(plan)
    p.blackout_status = BlackoutStatus(
        is_active=True,
        start_date="2026-06-20",
        end_date="2026-07-31",
        reason="Recordkeeper transition to Empower",
    )
    return p


@pytest.fixture
def no_loan_plan(plan):
    """PLAN-003 copy with loans disabled — tests loan_not_permitted denial."""
    p = copy.deepcopy(plan)
    p.loan_policy.loans_permitted = False
    return p


@pytest.fixture
def no_hardship_plan(plan):
    """PLAN-003 copy with hardship disabled."""
    p = copy.deepcopy(plan)
    p.hardship_policy.hardship_permitted = False
    return p


@pytest.fixture
def near_retirement_participant():
    """PART-006 Gabriel Stone: age 61, HCE, $185k comp, Capital One, age_50_or_older=True."""
    return copy.deepcopy(PART_006)


@pytest.fixture
def young_participant():
    """PART-007 Yuki Tanaka: 1.5yr service, unvested (below both 2yr and 3yr cliffs)."""
    return copy.deepcopy(PART_007)


@pytest.fixture
def loan_participant():
    """PART-009 Daniela Reyes: $100k vested, existing $25k loan → max additional = $25k."""
    return copy.deepcopy(PART_009)


# ---------------------------------------------------------------------------
# Rule 1 — Delegation Validity
# ---------------------------------------------------------------------------

class TestRule01DelegationValidity:

    def test_passes_for_registered_active_agent(self):
        result = rule_01_delegation_validity(
            "AGENT-PARTICIPANT-001", PrincipalType.participant,
            ActionType.loan_initiation, "PLAN-003"
        )
        assert result.passed

    def test_fails_for_unregistered_agent(self):
        result = rule_01_delegation_validity(
            "AGENT-GHOST-999", PrincipalType.participant,
            ActionType.loan_initiation, "PLAN-003"
        )
        assert not result.passed
        assert result.denial_code == DenialCode.agent_not_registered

    def test_fails_for_inactive_agent(self):
        result = rule_01_delegation_validity(
            "AGENT-INACTIVE-001", PrincipalType.participant,
            ActionType.loan_initiation, "PLAN-003"
        )
        assert not result.passed
        assert result.denial_code == DenialCode.agent_not_registered

    def test_fails_for_wrong_principal_type(self):
        # Advisor agent acting as participant principal
        result = rule_01_delegation_validity(
            "AGENT-ADVISOR-001", PrincipalType.participant,
            ActionType.investment_reallocation, "PLAN-003"
        )
        assert not result.passed
        assert result.denial_code == DenialCode.delegation_scope_exceeded

    def test_fails_for_action_not_in_scope(self):
        # Advisor cannot initiate loans
        result = rule_01_delegation_validity(
            "AGENT-ADVISOR-001", PrincipalType.investment_advisor,
            ActionType.loan_initiation, "PLAN-003"
        )
        assert not result.passed
        assert result.denial_code == DenialCode.delegation_scope_exceeded

    def test_fails_for_plan_not_in_scope(self):
        # AGENT-ADVISOR-001 is authorized for PLAN-003 only — not PLAN-004
        result = rule_01_delegation_validity(
            "AGENT-ADVISOR-001", PrincipalType.investment_advisor,
            ActionType.investment_reallocation, "PLAN-004"
        )
        assert not result.passed
        assert result.denial_code == DenialCode.delegation_scope_exceeded

    def test_passes_for_wildcard_plan_id(self):
        # Sponsor agent has allowed_plan_ids=["*"]
        result = rule_01_delegation_validity(
            "AGENT-SPONSOR-001", PrincipalType.plan_sponsor,
            ActionType.qdro, "PLAN-004"
        )
        assert result.passed


# ---------------------------------------------------------------------------
# Rule 2 — Blackout Period
# ---------------------------------------------------------------------------

class TestRule02BlackoutPeriod:

    def test_passes_when_no_blackout(self, plan):
        result = rule_02_blackout_period(plan, ActionType.loan_initiation)
        assert result.passed

    def test_fails_write_during_active_blackout(self, blackout_plan):
        result = rule_02_blackout_period(blackout_plan, ActionType.loan_initiation)
        assert not result.passed
        assert result.denial_code == DenialCode.blackout_active

    def test_fails_deferral_change_during_blackout(self, blackout_plan):
        result = rule_02_blackout_period(blackout_plan, ActionType.deferral_change)
        assert not result.passed

    def test_rmd_permitted_during_blackout(self, blackout_plan):
        # RMDs are a regulatory obligation — blackout cannot block them
        result = rule_02_blackout_period(blackout_plan, ActionType.rmd)
        assert result.passed


# ---------------------------------------------------------------------------
# Rule 3 — Participation and Eligibility
# ---------------------------------------------------------------------------

class TestRule03Eligibility:

    def test_passes_for_eligible_participant(self, participant, plan):
        result = rule_03_participation_eligibility(participant, plan, ActionType.loan_initiation)
        assert result.passed

    def test_passes_for_non_eligibility_gated_action(self, participant, plan):
        result = rule_03_participation_eligibility(participant, plan, ActionType.beneficiary_update)
        assert result.passed

    def test_fails_when_eligibility_date_in_future(self, participant, plan):
        participant.eligibility_date = "2099-01-01"
        result = rule_03_participation_eligibility(participant, plan, ActionType.deferral_change)
        assert not result.passed
        assert result.denial_code == DenialCode.entry_date_not_reached

    def test_fails_for_underage_participant(self, participant, plan):
        # Capital One eligibility_age=18 — set participant to age 16
        dob = date.today().replace(year=date.today().year - 16)
        participant.date_of_birth = dob.strftime("%Y-%m-%d")
        result = rule_03_participation_eligibility(participant, plan, ActionType.deferral_change)
        assert not result.passed
        assert result.denial_code == DenialCode.eligibility_not_met


# ---------------------------------------------------------------------------
# Rule 4 — Vesting Enforcement
# ---------------------------------------------------------------------------

class TestRule04Vesting:

    def test_passes_for_non_distribution_action(self, participant, plan):
        result = rule_04_vesting_enforcement(participant, plan, ActionType.deferral_change, {})
        assert result.passed

    def test_passes_for_fully_vested_participant(self, participant, plan):
        # Amara has 5yr service; Capital One 2yr cliff → fully vested
        assert participant.years_of_vesting_service >= 2.0
        result = rule_04_vesting_enforcement(
            participant, plan, ActionType.separation_distribution, {}
        )
        assert result.passed

    def test_fails_for_unvested_separation_distribution(self, young_participant, plan):
        # Yuki has 1.5yr service — below Capital One's 2yr cliff
        result = rule_04_vesting_enforcement(
            young_participant, plan, ActionType.separation_distribution, {}
        )
        assert not result.passed
        assert result.denial_code == DenialCode.insufficient_vesting

    def test_passes_employee_deferral_only_source(self, young_participant, plan):
        # Employee deferrals are always 100% vested — not blocked even if unvested in match
        result = rule_04_vesting_enforcement(
            young_participant, plan, ActionType.separation_distribution,
            {"source": "employee_deferrals_only"}
        )
        assert result.passed


# ---------------------------------------------------------------------------
# Rule 5 — Contribution Limits
# ---------------------------------------------------------------------------

class TestRule05ContributionLimits:

    def test_passes_for_non_deferral_action(self, participant):
        result = rule_05_contribution_limits(participant, ActionType.loan_initiation, {})
        assert result.passed

    def test_passes_for_reasonable_deferral(self, participant):
        # 6% of Amara's $92k = $5,520 — well under $23,000
        result = rule_05_contribution_limits(
            participant, ActionType.deferral_change, {"deferral_pct": 0.06}
        )
        assert result.passed

    def test_fails_when_deferral_exceeds_402g_limit(self, participant):
        # 50% of $92k = $46,000 — exceeds $23,000 limit
        result = rule_05_contribution_limits(
            participant, ActionType.deferral_change, {"deferral_pct": 0.50}
        )
        assert not result.passed
        assert result.denial_code == DenialCode.deferral_limit_exceeded

    def test_passes_catch_up_for_age_50_plus(self, near_retirement_participant):
        # Gabriel: age 61, $185k comp. 10% = $18,500 < $23k base — not even catch-up territory
        result = rule_05_contribution_limits(
            near_retirement_participant, ActionType.deferral_change, {"deferral_pct": 0.10}
        )
        assert result.passed

    def test_fails_annual_additions_415c(self, participant):
        # Force a scenario where total additions exceed IRC § 415(c) $69k cap
        participant.compensation_ytd = Decimal("345000")
        participant.employee_contributions_ytd = Decimal("23000")
        participant.employer_contributions_ytd = Decimal("46100")
        # 1% of $345k = $3,450 → total $72,550 > $69,000
        result = rule_05_contribution_limits(
            participant, ActionType.deferral_change, {"deferral_pct": 0.01}
        )
        assert not result.passed
        assert result.denial_code == DenialCode.annual_additions_limit_exceeded


# ---------------------------------------------------------------------------
# Rule 5 — SECURE 2.0 Roth Catch-Up (effective 2026)
# ---------------------------------------------------------------------------

class TestRule05RothCatchUp:

    def test_passes_catch_up_not_triggered_below_base(self, near_retirement_participant):
        # Gabriel: $185k comp, age_50_or_older=True. 10% = $18,500 < $23k — not catch-up
        result = rule_05_contribution_limits(
            near_retirement_participant, ActionType.deferral_change,
            {"deferral_pct": 0.10, "deferral_type": "pre_tax"}
        )
        assert result.passed

    def test_fails_high_earner_pre_tax_catchup(self, near_retirement_participant):
        # Gabriel: $185k > $145k threshold, age_50_or_older=True
        # 15% of $185k = $27,750 > $23k base → catch-up territory
        # deferral_type=pre_tax → SECURE 2.0 §603 requires Roth
        result = rule_05_contribution_limits(
            near_retirement_participant, ActionType.deferral_change,
            {"deferral_pct": 0.15, "deferral_type": "pre_tax"}
        )
        assert not result.passed
        assert result.denial_code == DenialCode.roth_catchup_required

    def test_passes_high_earner_roth_catchup(self, near_retirement_participant):
        # Same scenario, deferral_type=roth → complies with SECURE 2.0 §603
        result = rule_05_contribution_limits(
            near_retirement_participant, ActionType.deferral_change,
            {"deferral_pct": 0.15, "deferral_type": "roth"}
        )
        assert result.passed

    def test_fails_with_402g_not_roth_when_under_threshold(self, participant):
        # Amara: $92k < $145k threshold — Roth catch-up rule does NOT apply
        # Force age_50_or_older to test catch-up limit math
        participant.age_50_or_older = True
        participant.compensation_ytd = Decimal("92000")
        # 40% of $92k = $36,800 > $23k + $7.5k = $30,500 combined limit
        result = rule_05_contribution_limits(
            participant, ActionType.deferral_change,
            {"deferral_pct": 0.40, "deferral_type": "pre_tax"}
        )
        assert not result.passed
        # Should fail on 402g limit, NOT roth_catchup_required
        assert result.denial_code == DenialCode.deferral_limit_exceeded

    def test_passes_high_income_under_50_not_affected(self, participant):
        # Under 50 → catch-up rules do not apply regardless of income
        participant.age_50_or_older = False
        participant.compensation_ytd = Decimal("200000")
        # 10% of $200k = $20k < $23k base
        result = rule_05_contribution_limits(
            participant, ActionType.deferral_change,
            {"deferral_pct": 0.10, "deferral_type": "pre_tax"}
        )
        assert result.passed


# ---------------------------------------------------------------------------
# Rule 6 — Plan Rules (loan sub-rules)
# ---------------------------------------------------------------------------

class TestRule06LoanRules:

    def test_passes_valid_loan_request(self, participant, plan):
        # $20k on $85k vested → max = min($50k, 50% of $85k) = $42,500 → passes
        result = rule_06_plan_rules(
            participant, plan, ActionType.loan_initiation,
            {"amount": "20000", "repayment_years": 5, "purpose": "general"}
        )
        assert result.passed

    def test_fails_loan_exceeds_50pct_vested(self, participant, plan):
        # $50k > 50% of $85k = $42,500 cap
        result = rule_06_plan_rules(
            participant, plan, ActionType.loan_initiation,
            {"amount": "50000", "repayment_years": 5, "purpose": "general"}
        )
        assert not result.passed
        assert result.denial_code == DenialCode.loan_cap_exceeded

    def test_fails_loan_plan_not_permitted(self, participant, no_loan_plan):
        result = rule_06_plan_rules(
            participant, no_loan_plan, ActionType.loan_initiation,
            {"amount": "5000", "repayment_years": 5, "purpose": "general"}
        )
        assert not result.passed
        assert result.denial_code == DenialCode.loan_not_permitted

    def test_fails_existing_loan_reduces_cap(self, loan_participant, plan):
        # Daniela: $25k existing loan → IRS cap = $50k - $25k = $25k; 50% of $100k = $50k
        # Effective max = $25k; requesting $30k → BLOCKED
        result = rule_06_plan_rules(
            loan_participant, plan, ActionType.loan_initiation,
            {"amount": "30000", "repayment_years": 5, "purpose": "general"}
        )
        assert not result.passed
        assert result.denial_code == DenialCode.loan_cap_exceeded

    def test_passes_loan_under_reduced_cap(self, loan_participant, plan):
        # Requesting $20k — within the $25k reduced cap
        result = rule_06_plan_rules(
            loan_participant, plan, ActionType.loan_initiation,
            {"amount": "20000", "repayment_years": 5, "purpose": "general"}
        )
        assert result.passed

    def test_fails_repayment_term_too_long(self, participant, plan):
        # Capital One max_repayment_years_general = 5; 7 > 5 → BLOCKED
        result = rule_06_plan_rules(
            participant, plan, ActionType.loan_initiation,
            {"amount": "10000", "repayment_years": 7, "purpose": "general"}
        )
        assert not result.passed
        assert result.denial_code == DenialCode.loan_cap_exceeded

    def test_passes_primary_residence_extended_term(self, participant, plan):
        # Capital One max_repayment_years_primary_res = 10
        result = rule_06_plan_rules(
            participant, plan, ActionType.loan_initiation,
            {"amount": "10000", "repayment_years": 10, "purpose": "primary_residence"}
        )
        assert result.passed


# ---------------------------------------------------------------------------
# Rule 6 — Hardship sub-rules
# ---------------------------------------------------------------------------

class TestRule06HardshipRules:

    def test_passes_valid_hardship_expense(self, participant, plan):
        result = rule_06_plan_rules(
            participant, plan, ActionType.hardship_distribution,
            {"qualifying_expense_type": "medical", "amount": "5000"}
        )
        assert result.passed

    def test_fails_invalid_expense_type(self, participant, plan):
        result = rule_06_plan_rules(
            participant, plan, ActionType.hardship_distribution,
            {"qualifying_expense_type": "vacation", "amount": "5000"}
        )
        assert not result.passed
        assert result.denial_code == DenialCode.hardship_criteria_not_met

    def test_fails_hardship_plan_not_permitted(self, participant, no_hardship_plan):
        result = rule_06_plan_rules(
            participant, no_hardship_plan, ActionType.hardship_distribution,
            {"qualifying_expense_type": "medical", "amount": "5000"}
        )
        assert not result.passed
        assert result.denial_code == DenialCode.hardship_not_permitted


# ---------------------------------------------------------------------------
# Rule 6 — In-Service Distribution
# ---------------------------------------------------------------------------

class TestRule06InServiceDistribution:

    def test_fails_in_service_below_59_5(self, participant, plan):
        # Amara is 36 — well below 59½
        result = rule_06_plan_rules(
            participant, plan, ActionType.in_service_distribution, {}
        )
        assert not result.passed
        assert result.denial_code == DenialCode.in_service_age_not_met

    def test_passes_in_service_at_61(self, near_retirement_participant, plan):
        # Gabriel is 61 — over 59½
        result = rule_06_plan_rules(
            near_retirement_participant, plan, ActionType.in_service_distribution, {}
        )
        assert result.passed


# ---------------------------------------------------------------------------
# Rule 6 — Separation Distribution
# ---------------------------------------------------------------------------

class TestRule06SeparationDistribution:

    def test_fails_when_still_active(self, participant, plan):
        result = rule_06_plan_rules(
            participant, plan, ActionType.separation_distribution,
            {"rollover_402f_notice_confirmed": True}
        )
        assert not result.passed
        assert result.denial_code == DenialCode.separation_status_invalid

    def test_fails_when_no_rollover_notice(self, participant, plan):
        participant.employment_status = "terminated"
        result = rule_06_plan_rules(
            participant, plan, ActionType.separation_distribution, {}
        )
        assert not result.passed
        assert result.denial_code == DenialCode.rollover_notice_not_issued

    def test_passes_terminated_with_notice(self, participant, plan):
        participant.employment_status = "terminated"
        result = rule_06_plan_rules(
            participant, plan, ActionType.separation_distribution,
            {"rollover_402f_notice_confirmed": True}
        )
        assert result.passed


# ---------------------------------------------------------------------------
# Rule 6 — RMD notice gate
# ---------------------------------------------------------------------------

class TestRule06RmdNotice:

    def test_fails_rmd_without_notice(self, near_retirement_participant, plan):
        near_retirement_participant.rmd_required = True
        near_retirement_participant.rmd_amount_current_year = Decimal("12000")
        result = rule_06_plan_rules(
            near_retirement_participant, plan, ActionType.rmd,
            {"amount": "12000"}    # notice not confirmed
        )
        assert not result.passed
        assert result.denial_code == DenialCode.rmd_notice_not_issued

    def test_passes_rmd_with_notice_confirmed(self, near_retirement_participant, plan):
        near_retirement_participant.rmd_required = True
        near_retirement_participant.rmd_amount_current_year = Decimal("12000")
        result = rule_06_plan_rules(
            near_retirement_participant, plan, ActionType.rmd,
            {"amount": "12000", "rmd_notice_issued": True}
        )
        assert result.passed

    def test_fails_rmd_amount_below_required(self, near_retirement_participant, plan):
        near_retirement_participant.rmd_required = True
        near_retirement_participant.rmd_amount_current_year = Decimal("12000")
        result = rule_06_plan_rules(
            near_retirement_participant, plan, ActionType.rmd,
            {"amount": "5000", "rmd_notice_issued": True}
        )
        assert not result.passed
        assert result.denial_code == DenialCode.rmd_amount_insufficient

    def test_fails_rmd_not_yet_required(self, participant, plan):
        assert not participant.rmd_required
        result = rule_06_plan_rules(
            participant, plan, ActionType.rmd,
            {"amount": "5000", "rmd_notice_issued": True}
        )
        assert not result.passed
        assert result.denial_code == DenialCode.rmd_not_yet_required


# ---------------------------------------------------------------------------
# Rule 6 — Hardship legacy six_month_contribution_suspension
# ---------------------------------------------------------------------------

class TestRule06HardshipSuspensionCondition:

    def test_passes_without_condition_when_suspension_false(self, participant, plan):
        # Both Capital One and Prudential have six_month_contribution_suspension=False
        result = rule_06_plan_rules(
            participant, plan, ActionType.hardship_distribution,
            {"qualifying_expense_type": "medical", "amount": "5000"}
        )
        assert result.passed
        assert not result.conditions

    def test_passes_with_condition_when_suspension_true(self, participant, plan):
        # Simulate a legacy plan still enforcing the pre-2019 suspension election
        plan.hardship_policy.six_month_contribution_suspension = True
        result = rule_06_plan_rules(
            participant, plan, ActionType.hardship_distribution,
            {"qualifying_expense_type": "medical", "amount": "5000"}
        )
        assert result.passed          # approved — condition, not a block
        assert len(result.conditions) == 1
        assert "6 months" in result.conditions[0]


# ---------------------------------------------------------------------------
# Rule 7 — Early Withdrawal Penalty
# ---------------------------------------------------------------------------

class TestRule07EarlyWithdrawal:

    def test_passes_for_non_distribution_action(self, participant):
        result = rule_07_early_withdrawal_penalty(participant, ActionType.deferral_change, {})
        assert result.passed

    def test_passes_for_participant_over_59_5(self, near_retirement_participant):
        # Gabriel is 61 — no penalty
        result = rule_07_early_withdrawal_penalty(
            near_retirement_participant, ActionType.in_service_distribution, {}
        )
        assert result.passed

    def test_fails_for_participant_under_59_5_no_exception(self, participant):
        # Amara is 36 — penalty applies, no exception provided
        result = rule_07_early_withdrawal_penalty(
            participant, ActionType.in_service_distribution, {}
        )
        assert not result.passed
        assert result.denial_code == DenialCode.early_withdrawal_penalty_applies

    def test_passes_with_disability_exception(self, participant):
        result = rule_07_early_withdrawal_penalty(
            participant, ActionType.separation_distribution,
            {"penalty_exception": "disability"}
        )
        assert result.passed

    def test_passes_with_sepp_exception(self, participant):
        result = rule_07_early_withdrawal_penalty(
            participant, ActionType.separation_distribution,
            {"penalty_exception": "sepp_72t"}
        )
        assert result.passed

    def test_fails_separation_at_55_exception_when_too_young(self, participant):
        # Amara is 36 — cannot claim the age-55 separation exception
        result = rule_07_early_withdrawal_penalty(
            participant, ActionType.separation_distribution,
            {"penalty_exception": "separation_age_55"}
        )
        assert not result.passed

    def test_passes_secure_2_0_emergency_exception(self, participant):
        result = rule_07_early_withdrawal_penalty(
            participant, ActionType.separation_distribution,
            {"penalty_exception": "emergency_personal_expense"}
        )
        assert result.passed


# ---------------------------------------------------------------------------
# Rule 8 — Anti-Alienation
# ---------------------------------------------------------------------------

class TestRule08AntiAlienation:

    def test_passes_normal_loan_no_collateral(self):
        result = rule_08_anti_alienation(ActionType.loan_initiation, {})
        assert result.passed

    def test_fails_when_pledging_as_collateral(self):
        result = rule_08_anti_alienation(
            ActionType.separation_distribution, {"pledges_as_collateral": True}
        )
        assert not result.passed
        assert result.denial_code == DenialCode.anti_alienation_violation

    def test_passes_for_qdro(self):
        result = rule_08_anti_alienation(ActionType.qdro, {})
        assert result.passed


# ---------------------------------------------------------------------------
# Rule 9 — Prohibited Transaction
# ---------------------------------------------------------------------------

class TestRule09ProhibitedTransaction:

    def test_passes_standard_participant_transaction(self):
        result = rule_09_prohibited_transaction(
            PrincipalType.participant, ActionType.loan_initiation, {}
        )
        assert result.passed

    def test_fails_party_in_interest_transaction(self):
        result = rule_09_prohibited_transaction(
            PrincipalType.plan_sponsor, ActionType.deferral_change,
            {"counterparty_is_party_in_interest": True}
        )
        assert not result.passed
        assert result.denial_code == DenialCode.prohibited_transaction

    def test_fails_employer_securities_over_10_pct(self):
        # Capital One stock fund — >10% of plan assets is prohibited
        result = rule_09_prohibited_transaction(
            PrincipalType.participant, ActionType.investment_reallocation,
            {"involves_employer_securities": True, "employer_securities_pct": "0.15"}
        )
        assert not result.passed
        assert result.denial_code == DenialCode.prohibited_transaction

    def test_passes_employer_securities_under_10_pct(self):
        result = rule_09_prohibited_transaction(
            PrincipalType.participant, ActionType.investment_reallocation,
            {"involves_employer_securities": True, "employer_securities_pct": "0.08"}
        )
        assert result.passed

    def test_fails_advisor_distribution_without_pte(self):
        # Investment advisor recommending a distribution without PTE 2020-02 confirmation
        result = rule_09_prohibited_transaction(
            PrincipalType.investment_advisor, ActionType.separation_distribution, {}
        )
        assert not result.passed
        assert result.denial_code == DenialCode.prohibited_transaction


# ---------------------------------------------------------------------------
# Rule 10 — Prudent Expert and Loyalty
# ---------------------------------------------------------------------------

class TestRule10PrudentExpert:

    def test_passes_low_stakes_action(self):
        result = rule_10_prudent_expert_loyalty(ActionType.deferral_change, {})
        assert result.passed
        assert not result.conditions

    def test_passes_high_stakes_but_adds_condition(self):
        result = rule_10_prudent_expert_loyalty(ActionType.hardship_distribution, {})
        assert result.passed
        assert len(result.conditions) > 0


# ---------------------------------------------------------------------------
# Rule 11 — RMD Failure Prevention
# ---------------------------------------------------------------------------

class TestRule11RmdPrevention:

    def test_passes_when_rmd_not_required(self, participant):
        assert not participant.rmd_required
        result = rule_11_rmd_failure_prevention(
            participant, ActionType.separation_distribution, {}
        )
        assert result.passed

    def test_fails_when_rmd_outstanding_and_not_satisfied(self, near_retirement_participant):
        near_retirement_participant.rmd_required = True
        near_retirement_participant.rmd_amount_current_year = Decimal("15000")
        result = rule_11_rmd_failure_prevention(
            near_retirement_participant, ActionType.separation_distribution, {}
        )
        assert not result.passed
        assert result.denial_code == DenialCode.rmd_shortfall_risk

    def test_passes_when_rmd_satisfied(self, near_retirement_participant):
        near_retirement_participant.rmd_required = True
        near_retirement_participant.rmd_amount_current_year = Decimal("15000")
        result = rule_11_rmd_failure_prevention(
            near_retirement_participant, ActionType.separation_distribution,
            {"rmd_satisfied_for_year": True}
        )
        assert result.passed


# ---------------------------------------------------------------------------
# Rule 12 — Autonomy Level Assignment
# ---------------------------------------------------------------------------

class TestRule12AutonomyLevel:

    def test_full_for_deferral_increase(self):
        result = rule_12_autonomy_level(ActionType.deferral_change, {"deferral_pct": 0.10}, [])
        assert result.autonomy_level == AutonomyLevel.full

    def test_supervised_for_deferral_to_zero(self):
        result = rule_12_autonomy_level(ActionType.deferral_change, {"deferral_pct": 0.0}, [])
        assert result.autonomy_level == AutonomyLevel.supervised

    def test_supervised_for_loan_initiation(self):
        result = rule_12_autonomy_level(ActionType.loan_initiation, {}, [])
        assert result.autonomy_level == AutonomyLevel.supervised

    def test_human_review_for_hardship(self):
        result = rule_12_autonomy_level(ActionType.hardship_distribution, {}, [])
        assert result.autonomy_level == AutonomyLevel.human_review

    def test_human_review_for_qdro(self):
        result = rule_12_autonomy_level(ActionType.qdro, {}, [])
        assert result.autonomy_level == AutonomyLevel.human_review

    def test_human_review_for_separation_distribution(self):
        result = rule_12_autonomy_level(ActionType.separation_distribution, {}, [])
        assert result.autonomy_level == AutonomyLevel.human_review

    def test_full_for_investment_reallocation(self):
        result = rule_12_autonomy_level(ActionType.investment_reallocation, {}, [])
        assert result.autonomy_level == AutonomyLevel.full

    def test_address_update_gets_full_autonomy(self):
        result = rule_12_autonomy_level(ActionType.address_update, {}, [])
        assert result.passed
        assert result.autonomy_level == AutonomyLevel.full


# ---------------------------------------------------------------------------
# Full orchestrator — run_compliance_check end-to-end
# ---------------------------------------------------------------------------

class TestRunComplianceCheckEndToEnd:

    def test_approved_loan_primary_demo(self, participant, plan):
        """Amara requests $20k on $85k vested → approved, supervised."""
        result = run_compliance_check(
            agent_id="AGENT-PARTICIPANT-001",
            principal_type=PrincipalType.participant,
            participant=participant,
            plan=plan,
            action=ActionType.loan_initiation,
            payload={"amount": "20000", "repayment_years": 5, "purpose": "general"},
        )
        assert result.passed
        assert result.autonomy_level == AutonomyLevel.supervised

    def test_blocked_loan_exceeds_cap(self, participant, plan):
        """$50k request on $85k vested (max $42,500) → LOAN_CAP_EXCEEDED."""
        result = run_compliance_check(
            agent_id="AGENT-PARTICIPANT-001",
            principal_type=PrincipalType.participant,
            participant=participant,
            plan=plan,
            action=ActionType.loan_initiation,
            payload={"amount": "50000", "repayment_years": 5, "purpose": "general"},
        )
        assert not result.passed
        assert result.denial_code == DenialCode.loan_cap_exceeded
        assert result.rule_number == 6

    def test_blocked_by_blackout(self, participant, blackout_plan):
        """Loan blocked because plan is in active blackout — fails at rule 2."""
        result = run_compliance_check(
            agent_id="AGENT-PARTICIPANT-001",
            principal_type=PrincipalType.participant,
            participant=participant,
            plan=blackout_plan,
            action=ActionType.loan_initiation,
            payload={"amount": "10000", "repayment_years": 5, "purpose": "general"},
        )
        assert not result.passed
        assert result.denial_code == DenialCode.blackout_active
        assert result.rule_number == 2

    def test_blocked_by_unregistered_agent(self, participant, plan):
        """Unknown agent fails at rule 1."""
        result = run_compliance_check(
            agent_id="AGENT-UNKNOWN",
            principal_type=PrincipalType.participant,
            participant=participant,
            plan=plan,
            action=ActionType.loan_initiation,
            payload={"amount": "10000", "repayment_years": 5, "purpose": "general"},
        )
        assert not result.passed
        assert result.rule_number == 1

    def test_deferral_increase_full_autonomy(self, participant, plan):
        """Deferral increase approved at full autonomy."""
        result = run_compliance_check(
            agent_id="AGENT-PARTICIPANT-001",
            principal_type=PrincipalType.participant,
            participant=participant,
            plan=plan,
            action=ActionType.deferral_change,
            payload={"deferral_pct": 0.08, "deferral_type": "pre_tax"},
        )
        assert result.passed
        assert result.autonomy_level == AutonomyLevel.full

    def test_hardship_routes_to_human_review(self, participant, plan):
        """Valid hardship request approved at human_review autonomy."""
        result = run_compliance_check(
            agent_id="AGENT-PARTICIPANT-001",
            principal_type=PrincipalType.participant,
            participant=participant,
            plan=plan,
            action=ActionType.hardship_distribution,
            payload={
                "qualifying_expense_type": "medical",
                "amount": "5000",
                "documentation_refs": ["doc-001"],
            },
        )
        assert result.passed
        assert result.autonomy_level == AutonomyLevel.human_review

    def test_early_withdrawal_blocked_without_exception(self, participant, plan):
        """Pre-59½ separation distribution without exception → blocked at rule 7."""
        participant.employment_status = "terminated"
        result = run_compliance_check(
            agent_id="AGENT-PARTICIPANT-001",
            principal_type=PrincipalType.participant,
            participant=participant,
            plan=plan,
            action=ActionType.separation_distribution,
            payload={"rollover_402f_notice_confirmed": True},
        )
        assert not result.passed
        assert result.denial_code == DenialCode.early_withdrawal_penalty_applies
        assert result.rule_number == 7

    def test_address_update_end_to_end_approved(self, participant, plan):
        result = run_compliance_check(
            agent_id="AGENT-PARTICIPANT-001",
            principal_type=PrincipalType.participant,
            participant=participant,
            plan=plan,
            action=ActionType.address_update,
            payload={"new_street": "100 Main St", "new_city": "McLean", "new_state": "VA"},
        )
        assert result.passed
        assert result.autonomy_level == AutonomyLevel.full

    def test_prudential_loan_approved(self, young_participant, prudential_plan):
        """Yuki can take a loan on Prudential even though unvested (loans don't require vesting)."""
        # Make Yuki eligible first (set eligibility_date in past)
        young_participant.eligibility_date = "2025-07-01"
        result = run_compliance_check(
            agent_id="AGENT-PARTICIPANT-001",
            principal_type=PrincipalType.participant,
            participant=young_participant,
            plan=prudential_plan,
            action=ActionType.loan_initiation,
            payload={"amount": "10000", "repayment_years": 5, "purpose": "general"},
        )
        assert result.passed
        assert result.autonomy_level == AutonomyLevel.supervised
