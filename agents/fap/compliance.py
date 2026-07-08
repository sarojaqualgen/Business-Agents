"""
FAP 12-Rule ERISA Compliance Engine.

Rules are evaluated in order. Failure at any rule stops evaluation and returns
a denial immediately. All rules are pure Python functions — no CrewAI dependency —
so they can be tested independently with pytest.

Each rule returns a RuleResult. The orchestrator (run_compliance_check) stops at
the first failure and returns that result, or returns the Rule 12 result (autonomy
level assignment) if all rules pass.
"""

from datetime import date, datetime
from decimal import Decimal
from typing import Any

from agents.fap.models import (
    ActionType,
    AutonomyLevel,
    DenialCode,
    PrincipalType,
    RuleResult,
)
from agents.plap.models import PlanRecord, QualifyingExpenseType
from agents.paap.models import ParticipantRecord

# ---------------------------------------------------------------------------
# Internal registry (mock) — agent_id → AgentRegistration
# In production this hits a real identity store.
# ---------------------------------------------------------------------------
from data.agents import AGENT_REGISTRY


# ---------------------------------------------------------------------------
# Helper utilities
# ---------------------------------------------------------------------------

def _age_on(dob: str, reference_date: date | None = None) -> float:
    """Return age in years (fractional) as of reference_date (default: today)."""
    ref = reference_date or date.today()
    born = datetime.strptime(dob, "%Y-%m-%d").date()
    delta = ref - born
    return delta.days / 365.25


def _current_year() -> int:
    return date.today().year


# ---------------------------------------------------------------------------
# Rule 1 — Delegation Validity
# ERISA § 404 — Master Ref §6.1, §6.2
# ---------------------------------------------------------------------------

def rule_01_delegation_validity(
    agent_id: str,
    principal_type: PrincipalType,
    action: ActionType,
    plan_id: str,
) -> RuleResult:
    reg = AGENT_REGISTRY.get(agent_id)

    if reg is None or not reg.is_active:
        return RuleResult(
            passed=False,
            rule_number=1,
            rule_name="Delegation Validity",
            denial_code=DenialCode.agent_not_registered,
            denial_reason=f"Agent '{agent_id}' is not registered or is inactive.",
            erisa_citation="ERISA § 404",
            master_ref_section="§6.1, §6.2",
        )

    if reg.principal_type != principal_type:
        return RuleResult(
            passed=False,
            rule_number=1,
            rule_name="Delegation Validity",
            denial_code=DenialCode.delegation_scope_exceeded,
            denial_reason=(
                f"Agent '{agent_id}' is registered as {reg.principal_type} "
                f"but request uses principal_type={principal_type}."
            ),
            erisa_citation="ERISA § 404",
            master_ref_section="§6.1",
        )

    if action not in reg.allowed_actions:
        return RuleResult(
            passed=False,
            rule_number=1,
            rule_name="Delegation Validity",
            denial_code=DenialCode.delegation_scope_exceeded,
            denial_reason=f"Agent '{agent_id}' delegation does not cover action '{action}'.",
            erisa_citation="ERISA § 404",
            master_ref_section="§6.2",
        )

    if plan_id not in reg.allowed_plan_ids and "*" not in reg.allowed_plan_ids:
        return RuleResult(
            passed=False,
            rule_number=1,
            rule_name="Delegation Validity",
            denial_code=DenialCode.delegation_scope_exceeded,
            denial_reason=f"Agent '{agent_id}' is not authorized for plan '{plan_id}'.",
            erisa_citation="ERISA § 404",
            master_ref_section="§6.1",
        )

    return RuleResult(passed=True, rule_number=1, rule_name="Delegation Validity")


# ---------------------------------------------------------------------------
# Rule 2 — Blackout Period Check
# ERISA § 101(i) — Master Ref §7.7
# ---------------------------------------------------------------------------

def rule_02_blackout_period(plan: PlanRecord, action: ActionType) -> RuleResult:
    # Read-only actions are always permitted during blackout.
    read_only_actions = {ActionType.rmd}  # RMDs may still be processed; writes are blocked
    if plan.blackout_status.is_active and action not in read_only_actions:
        return RuleResult(
            passed=False,
            rule_number=2,
            rule_name="Blackout Period Check",
            denial_code=DenialCode.blackout_active,
            denial_reason=(
                f"Plan '{plan.plan_id}' is in an active blackout period "
                f"({plan.blackout_status.start_date} – {plan.blackout_status.end_date}). "
                f"Reason: {plan.blackout_status.reason}."
            ),
            erisa_citation="ERISA § 101(i)",
            master_ref_section="§7.7",
        )

    return RuleResult(passed=True, rule_number=2, rule_name="Blackout Period Check")


# ---------------------------------------------------------------------------
# Rule 3 — Participation and Eligibility
# ERISA § 202 / IRC § 410(a) — Master Ref §2.2, §2.3, §2.4
# ---------------------------------------------------------------------------

def rule_03_participation_eligibility(
    participant: ParticipantRecord,
    plan: PlanRecord,
    action: ActionType,
) -> RuleResult:
    # Only contribution and distribution actions require eligibility check.
    eligibility_gated_actions = {
        ActionType.deferral_change,
        ActionType.investment_reallocation,
        ActionType.loan_initiation,
        ActionType.hardship_distribution,
        ActionType.in_service_distribution,
        ActionType.separation_distribution,
        ActionType.rmd,
    }

    if action not in eligibility_gated_actions:
        return RuleResult(passed=True, rule_number=3, rule_name="Participation and Eligibility")

    # Use plan-configured minimum age — ERISA § 202 caps maximum at 21, plans may set lower.
    age = _age_on(participant.date_of_birth)
    min_age = plan.eligibility_age
    if age < min_age:
        return RuleResult(
            passed=False,
            rule_number=3,
            rule_name="Participation and Eligibility",
            denial_code=DenialCode.eligibility_not_met,
            denial_reason=f"Participant age {age:.1f} is below this plan's minimum participation age of {min_age}.",
            erisa_citation="ERISA § 202 / IRC § 410(a)",
            master_ref_section="§2.2",
        )

    today = date.today()
    eligibility_date = datetime.strptime(participant.eligibility_date, "%Y-%m-%d").date()
    if today < eligibility_date:
        return RuleResult(
            passed=False,
            rule_number=3,
            rule_name="Participation and Eligibility",
            denial_code=DenialCode.entry_date_not_reached,
            denial_reason=(
                f"Participant's effective eligibility date ({participant.eligibility_date}) "
                f"has not yet been reached (today: {today})."
            ),
            erisa_citation="ERISA § 202 / IRC § 410(a)",
            master_ref_section="§2.4",
        )

    return RuleResult(passed=True, rule_number=3, rule_name="Participation and Eligibility")


# ---------------------------------------------------------------------------
# Rule 4 — Vesting Enforcement
# ERISA § 203 / IRC § 411 — Master Ref §3.1, §3.2
# ---------------------------------------------------------------------------

def rule_04_vesting_enforcement(
    participant: ParticipantRecord,
    plan: PlanRecord,
    action: ActionType,
    payload: dict[str, Any],
) -> RuleResult:
    # Vesting only gates distribution of employer contributions.
    distribution_actions = {
        ActionType.in_service_distribution,
        ActionType.separation_distribution,
        ActionType.hardship_distribution,
    }

    if action not in distribution_actions:
        return RuleResult(passed=True, rule_number=4, rule_name="Vesting Enforcement")

    # Employee deferrals are always 100% vested (ERISA § 203 / Master Ref §3.1).
    # If the distribution is only from employee deferrals, no block.
    source = payload.get("source", "all")
    if source == "employee_deferrals_only":
        return RuleResult(passed=True, rule_number=4, rule_name="Vesting Enforcement")

    computed_pct = plan.match_vesting_schedule.vesting_pct_at_years(
        participant.years_of_vesting_service
    )

    # Sync check: model's stored percentage should match computed.
    # We use the computed value as authoritative.
    if computed_pct < 1.0 and action in {ActionType.separation_distribution, ActionType.in_service_distribution}:
        return RuleResult(
            passed=False,
            rule_number=4,
            rule_name="Vesting Enforcement",
            denial_code=DenialCode.insufficient_vesting,
            denial_reason=(
                f"Participant has {participant.years_of_vesting_service:.1f} years of service "
                f"and is only {computed_pct*100:.0f}% vested in employer contributions. "
                f"Distribution must be limited to vested portion."
            ),
            erisa_citation="ERISA § 203 / IRC § 411",
            master_ref_section="§3.2",
        )

    return RuleResult(passed=True, rule_number=4, rule_name="Vesting Enforcement")


# ---------------------------------------------------------------------------
# Rule 5 — Contribution Limit Enforcement
# IRC §§ 402(g), 414(v), 415(c), 401(a)(17) — Master Ref §4.2
# ---------------------------------------------------------------------------

LIMIT_402G = Decimal("23000")           # 2024 employee elective deferral
LIMIT_414V_50 = Decimal("7500")         # 2024 catch-up age 50+
LIMIT_414V_60_63 = Decimal("10000")     # 2025+ catch-up ages 60-63
LIMIT_415C = Decimal("69000")           # 2024 total annual additions
LIMIT_COMP_CAP = Decimal("345000")      # 2024 compensation cap
LIMIT_ROTH_CATCHUP_INCOME = Decimal("145000")  # SECURE 2.0 §603 — mandatory Roth catch-up for high earners, effective 2026


def rule_05_contribution_limits(
    participant: ParticipantRecord,
    action: ActionType,
    payload: dict[str, Any],
) -> RuleResult:
    if action != ActionType.deferral_change:
        return RuleResult(passed=True, rule_number=5, rule_name="Contribution Limits")

    new_deferral_pct = Decimal(str(
        payload["deferral_pct"] if "deferral_pct" in payload
        else payload.get("new_deferral_pct", 0)
    ))
    capped_comp = min(participant.compensation_ytd, LIMIT_COMP_CAP)
    projected_annual_deferral = capped_comp * new_deferral_pct

    # Base 402(g) limit
    base_limit = LIMIT_402G

    # Catch-up limit
    if participant.age_60_to_63:
        # SECURE 2.0: greater of $10,000 or 150% of regular catch-up
        catchup = max(LIMIT_414V_60_63, LIMIT_414V_50 * Decimal("1.5"))
    elif participant.age_50_or_older:
        catchup = LIMIT_414V_50
    else:
        catchup = Decimal("0")

    effective_402g_limit = base_limit + catchup

    if projected_annual_deferral > effective_402g_limit:
        return RuleResult(
            passed=False,
            rule_number=5,
            rule_name="Contribution Limits",
            denial_code=DenialCode.deferral_limit_exceeded,
            denial_reason=(
                f"Projected annual deferral of ${projected_annual_deferral:,.0f} exceeds "
                f"the IRC § 402(g) limit of ${effective_402g_limit:,.0f} "
                f"(base ${base_limit:,} + catch-up ${catchup:,})."
            ),
            erisa_citation="IRC § 402(g)(1) / IRC § 414(v)",
            master_ref_section="§4.2",
        )

    # 415(c) total annual additions check
    projected_total = (
        participant.employee_contributions_ytd
        + participant.employer_contributions_ytd
        + projected_annual_deferral
    )
    limit_415c = min(LIMIT_415C, capped_comp)
    if projected_total > limit_415c:
        return RuleResult(
            passed=False,
            rule_number=5,
            rule_name="Contribution Limits",
            denial_code=DenialCode.annual_additions_limit_exceeded,
            denial_reason=(
                f"Projected total annual additions of ${projected_total:,.0f} exceeds "
                f"the IRC § 415(c) limit of ${limit_415c:,.0f}."
            ),
            erisa_citation="IRC § 415(c)",
            master_ref_section="§4.2",
        )

    # SECURE 2.0 § 603 (effective 2026): catch-up contributions for participants earning
    # over $145,000 must be designated Roth. Enforce now — today's date is 2026.
    if participant.age_50_or_older and participant.compensation_ytd > LIMIT_ROTH_CATCHUP_INCOME:
        deferral_type = payload.get("deferral_type", "pre_tax")
        if projected_annual_deferral > LIMIT_402G and deferral_type == "pre_tax":
            return RuleResult(
                passed=False,
                rule_number=5,
                rule_name="Contribution Limits",
                denial_code=DenialCode.roth_catchup_required,
                denial_reason=(
                    f"SECURE 2.0 (effective 2026): participants earning over "
                    f"${LIMIT_ROTH_CATCHUP_INCOME:,.0f} must designate catch-up contributions as Roth. "
                    f"Projected deferral of ${projected_annual_deferral:,.0f} exceeds the base "
                    f"${LIMIT_402G:,} limit and compensation of ${participant.compensation_ytd:,.0f} "
                    f"exceeds the threshold. Set deferral_type='roth' to proceed."
                ),
                erisa_citation="IRC § 414(v)(7) / SECURE 2.0 Act § 603",
                master_ref_section="§4.2",
            )

    return RuleResult(passed=True, rule_number=5, rule_name="Contribution Limits")


# ---------------------------------------------------------------------------
# Rule 6 — Plan Rule Enforcement (sourced from PLAP)
# Various IRC provisions — Master Ref §5.x
# ---------------------------------------------------------------------------

def rule_06_plan_rules(
    participant: ParticipantRecord,
    plan: PlanRecord,
    action: ActionType,
    payload: dict[str, Any],
) -> RuleResult:

    if action == ActionType.loan_initiation:
        return _check_loan_rules(participant, plan, payload)

    if action == ActionType.hardship_distribution:
        return _check_hardship_rules(participant, plan, payload)

    if action == ActionType.in_service_distribution:
        return _check_in_service_rules(participant, plan)

    if action == ActionType.separation_distribution:
        return _check_separation_rules(participant, payload)

    if action == ActionType.rmd:
        return _check_rmd_rules(participant, payload)

    if action == ActionType.beneficiary_update:
        return _check_beneficiary_rules(participant, plan, payload)

    if action == ActionType.qdro:
        return _check_qdro_rules(plan, payload)

    return RuleResult(passed=True, rule_number=6, rule_name="Plan Rule Enforcement")


def _check_loan_rules(
    participant: ParticipantRecord,
    plan: PlanRecord,
    payload: dict[str, Any],
) -> RuleResult:
    lp = plan.loan_policy

    if not lp.loans_permitted:
        return RuleResult(
            passed=False,
            rule_number=6,
            rule_name="Plan Rule Enforcement",
            denial_code=DenialCode.loan_not_permitted,
            denial_reason="This plan does not permit participant loans.",
            erisa_citation="IRC § 72(p)",
            master_ref_section="§5.5",
        )

    if len(participant.outstanding_loans) >= lp.outstanding_loans_permitted:
        return RuleResult(
            passed=False,
            rule_number=6,
            rule_name="Plan Rule Enforcement",
            denial_code=DenialCode.loans_outstanding_limit,
            denial_reason=(
                f"Participant already has {len(participant.outstanding_loans)} outstanding loan(s). "
                f"This plan permits a maximum of {lp.outstanding_loans_permitted}."
            ),
            erisa_citation="IRC § 72(p)",
            master_ref_section="§5.5",
        )

    requested_amount = Decimal(str(payload.get("amount", 0)))
    max_allowed = participant.max_additional_loan_amount

    if requested_amount > max_allowed:
        return RuleResult(
            passed=False,
            rule_number=6,
            rule_name="Plan Rule Enforcement",
            denial_code=DenialCode.loan_cap_exceeded,
            denial_reason=(
                f"Requested loan of ${requested_amount:,.0f} exceeds the maximum allowed "
                f"amount of ${max_allowed:,.0f} "
                f"(lesser of $50,000 minus prior loan balances or 50% of vested balance "
                f"${participant.vested_balance:,.0f})."
            ),
            erisa_citation="IRC § 72(p)",
            master_ref_section="§5.5",
        )

    repayment_years = int(payload.get("repayment_years", 5))
    purpose = payload.get("purpose", "general")
    max_term = lp.primary_residence_extension_years if purpose == "primary_residence" else lp.max_repayment_years
    if repayment_years > max_term:
        return RuleResult(
            passed=False,
            rule_number=6,
            rule_name="Plan Rule Enforcement",
            denial_code=DenialCode.loan_cap_exceeded,
            denial_reason=(
                f"Requested repayment term of {repayment_years} years exceeds the plan maximum "
                f"of {max_term} years for purpose='{purpose}'."
            ),
            erisa_citation="IRC § 72(p)",
            master_ref_section="§5.5",
        )

    return RuleResult(passed=True, rule_number=6, rule_name="Plan Rule Enforcement")


def _check_hardship_rules(
    participant: ParticipantRecord,
    plan: PlanRecord,
    payload: dict[str, Any],
) -> RuleResult:
    hp = plan.hardship_policy

    if not hp.hardship_permitted:
        return RuleResult(
            passed=False,
            rule_number=6,
            rule_name="Plan Rule Enforcement",
            denial_code=DenialCode.hardship_not_permitted,
            denial_reason="This plan does not permit hardship distributions.",
            erisa_citation="IRC § 401(k)(2)(B)(i)(IV)",
            master_ref_section="§5.4",
        )

    # Accept both key names — tool description uses qualifying_expense_type;
    # fall back to expense_type so LLM variation doesn't silently fail.
    expense_type_str = (
        payload.get("qualifying_expense_type")
        or payload.get("expense_type")
        or ""
    )
    try:
        expense_type = QualifyingExpenseType(expense_type_str)
    except ValueError:
        return RuleResult(
            passed=False,
            rule_number=6,
            rule_name="Plan Rule Enforcement",
            denial_code=DenialCode.hardship_criteria_not_met,
            denial_reason=f"Expense type '{expense_type_str}' is not a recognized hardship category.",
            erisa_citation="IRC § 401(k)(2)(B)(i)(IV)",
            master_ref_section="§5.4",
        )

    if expense_type not in hp.qualifying_expenses:
        return RuleResult(
            passed=False,
            rule_number=6,
            rule_name="Plan Rule Enforcement",
            denial_code=DenialCode.hardship_criteria_not_met,
            denial_reason=(
                f"Expense type '{expense_type_str}' is not in this plan's approved "
                f"hardship expense list."
            ),
            erisa_citation="IRC § 401(k)(2)(B)(i)(IV)",
            master_ref_section="§5.4",
        )

    conditions = []
    if hp.six_month_contribution_suspension:
        # Pre-2019 plan still in force: post-2018 regulations eliminated this requirement
        # but plans that elected it before 2019 may retain it. Surface as a condition for
        # the human reviewer.
        conditions.append(
            "Legacy plan provision: this plan suspends employee contributions for 6 months "
            "following a hardship distribution (pre-2019 election still in force). "
            "Participant will be notified that they cannot resume contributions until the "
            "suspension period ends."
        )

    return RuleResult(passed=True, rule_number=6, rule_name="Plan Rule Enforcement", conditions=conditions)


def _check_in_service_rules(
    participant: ParticipantRecord,
    plan: PlanRecord,
) -> RuleResult:
    if not plan.distribution_options.in_service_age_59_5:
        return RuleResult(
            passed=False,
            rule_number=6,
            rule_name="Plan Rule Enforcement",
            denial_code=DenialCode.in_service_age_not_met,
            denial_reason="This plan does not permit in-service distributions.",
            erisa_citation="IRC § 401(a)",
            master_ref_section="§5.1",
        )

    age = _age_on(participant.date_of_birth)
    if age < 59.5:
        return RuleResult(
            passed=False,
            rule_number=6,
            rule_name="Plan Rule Enforcement",
            denial_code=DenialCode.in_service_age_not_met,
            denial_reason=(
                f"In-service distributions require age 59½. "
                f"Participant's current age is {age:.1f}."
            ),
            erisa_citation="IRC § 401(a)",
            master_ref_section="§5.1",
        )

    return RuleResult(passed=True, rule_number=6, rule_name="Plan Rule Enforcement")


def _check_separation_rules(
    participant: ParticipantRecord,
    payload: dict[str, Any],
) -> RuleResult:
    if participant.employment_status not in {"terminated", "retired"}:
        return RuleResult(
            passed=False,
            rule_number=6,
            rule_name="Plan Rule Enforcement",
            denial_code=DenialCode.separation_status_invalid,
            denial_reason=(
                f"Separation distributions require employment_status of 'terminated' or 'retired'. "
                f"Current status: '{participant.employment_status.value}'."
            ),
            erisa_citation="IRC § 402",
            master_ref_section="§5.1",
        )

    rollover_notice_confirmed = (
        payload["rollover_402f_notice_confirmed"] if "rollover_402f_notice_confirmed" in payload
        else payload.get("rollover_notice_issued", False)
    )
    if not rollover_notice_confirmed:
        return RuleResult(
            passed=False,
            rule_number=6,
            rule_name="Plan Rule Enforcement",
            denial_code=DenialCode.rollover_notice_not_issued,
            denial_reason=(
                "IRC § 402(f) rollover notice must be provided 30–180 days before a separation distribution. "
                "Set rollover_402f_notice_confirmed=True in the payload once the notice has been sent."
            ),
            erisa_citation="IRC § 402 / ERISA § 101",
            master_ref_section="§7.7",
        )

    return RuleResult(passed=True, rule_number=6, rule_name="Plan Rule Enforcement")


def _check_rmd_rules(
    participant: ParticipantRecord,
    payload: dict[str, Any],
) -> RuleResult:
    if not participant.rmd_required:
        return RuleResult(
            passed=False,
            rule_number=6,
            rule_name="Plan Rule Enforcement",
            denial_code=DenialCode.rmd_not_yet_required,
            denial_reason="Participant has not yet reached the required minimum distribution age.",
            erisa_citation="IRC § 401(a)(9)",
            master_ref_section="§5.2",
        )

    # Agent Definitions §8: RMD notice must be issued by January 31 before processing.
    rmd_notice_issued = payload.get("rmd_notice_issued", False)
    if not rmd_notice_issued:
        return RuleResult(
            passed=False,
            rule_number=6,
            rule_name="Plan Rule Enforcement",
            denial_code=DenialCode.rmd_notice_not_issued,
            denial_reason=(
                "RMD notice must be issued to the participant by January 31 of the distribution year "
                "before processing the RMD. Set rmd_notice_issued=True in the payload once the "
                "notice has been delivered."
            ),
            erisa_citation="IRC § 401(a)(9) / ERISA § 101",
            master_ref_section="§7.7",
        )

    requested_amount = Decimal(str(payload.get("amount", 0)))
    if participant.rmd_amount_current_year and requested_amount < participant.rmd_amount_current_year:
        return RuleResult(
            passed=False,
            rule_number=6,
            rule_name="Plan Rule Enforcement",
            denial_code=DenialCode.rmd_amount_insufficient,
            denial_reason=(
                f"RMD distribution of ${requested_amount:,.0f} is below the required "
                f"${participant.rmd_amount_current_year:,.0f} for the current plan year."
            ),
            erisa_citation="IRC § 401(a)(9)",
            master_ref_section="§5.2",
        )

    return RuleResult(passed=True, rule_number=6, rule_name="Plan Rule Enforcement")


def _check_beneficiary_rules(
    participant: ParticipantRecord,
    plan: PlanRecord,
    payload: dict[str, Any],
) -> RuleResult:
    # FAP handles QJSA internally — it receives a boolean indicating if spousal consent was obtained.
    # It never receives marital status directly (PII rule).
    spousal_consent_obtained = payload.get("spousal_consent_obtained", None)

    # If the plan requires spousal consent and it's not confirmed, block.
    if plan.distribution_options.qjsa_waiver_requires_spousal_consent:
        if spousal_consent_obtained is None:
            # We don't know — surface conditions but do not block outright;
            # this routes to human_review for verification.
            return RuleResult(
                passed=True,
                rule_number=6,
                rule_name="Plan Rule Enforcement",
                conditions=["Spousal consent status not confirmed — human review required."],
            )
        if spousal_consent_obtained is False:
            return RuleResult(
                passed=False,
                rule_number=6,
                rule_name="Plan Rule Enforcement",
                denial_code=DenialCode.qjsa_consent_required,
                denial_reason=(
                    "This plan requires written spousal consent (witnessed by a plan representative "
                    "or notary public) for beneficiary changes under ERISA § 205."
                ),
                erisa_citation="ERISA § 205 / IRC § 401(a)(11)",
                master_ref_section="§5.7",
            )

    return RuleResult(passed=True, rule_number=6, rule_name="Plan Rule Enforcement")


def _check_qdro_rules(
    plan: PlanRecord,
    payload: dict[str, Any],
) -> RuleResult:
    required = plan.rollover_qdro.qdro_required_fields
    missing = [f for f in required if not payload.get(f)]
    if missing:
        return RuleResult(
            passed=False,
            rule_number=6,
            rule_name="Plan Rule Enforcement",
            denial_code=DenialCode.qdro_fields_missing,
            denial_reason=f"QDRO is missing required fields: {', '.join(missing)}.",
            erisa_citation="ERISA § 206(d) / IRC § 414(p)",
            master_ref_section="§5.6",
        )

    return RuleResult(passed=True, rule_number=6, rule_name="Plan Rule Enforcement")


# ---------------------------------------------------------------------------
# Rule 7 — Early Withdrawal Penalty Check
# IRC § 72(t) — Master Ref §5.3
# ---------------------------------------------------------------------------

def rule_07_early_withdrawal_penalty(
    participant: ParticipantRecord,
    action: ActionType,
    payload: dict[str, Any],
) -> RuleResult:
    # Only distributions can trigger the early withdrawal penalty.
    # hardship_distribution is always routed to human_review (Rule 12), so we don't
    # block it here — the human reviewer handles penalty disclosure. We just add a condition.
    agent_discretion_actions = {
        ActionType.in_service_distribution,
        ActionType.separation_distribution,
    }
    informational_actions = {
        ActionType.hardship_distribution,
    }

    if action not in agent_discretion_actions and action not in informational_actions:
        return RuleResult(passed=True, rule_number=7, rule_name="Early Withdrawal Penalty Check")

    age = _age_on(participant.date_of_birth)
    if age >= 59.5:
        return RuleResult(passed=True, rule_number=7, rule_name="Early Withdrawal Penalty Check")

    # Check for valid exceptions
    exception = payload.get("penalty_exception")
    valid_exceptions = {
        "separation_age_55",        # Separation at age 55+
        "disability",
        "death_beneficiary",
        "sepp_72t",
        "qdro",
        "medical_expenses",
        "qualified_reservist",
        "birth_or_adoption",
        "emergency_personal_expense",  # SECURE 2.0 2024
        "domestic_abuse_victim",       # SECURE 2.0 2024
        "terminal_illness",            # SECURE 2.0 2024
    }

    if exception == "separation_age_55":
        if age < 55:
            return RuleResult(
                passed=False,
                rule_number=7,
                rule_name="Early Withdrawal Penalty Check",
                denial_code=DenialCode.early_withdrawal_penalty_applies,
                denial_reason=(
                    f"Separation-at-55 exception claimed, but participant age is {age:.1f}. "
                    f"Must be at least 55 at separation."
                ),
                erisa_citation="IRC § 72(t)(2)(A)(v)",
                master_ref_section="§5.3",
            )
        return RuleResult(passed=True, rule_number=7, rule_name="Early Withdrawal Penalty Check")

    if exception in valid_exceptions:
        return RuleResult(passed=True, rule_number=7, rule_name="Early Withdrawal Penalty Check")

    # Hardship distributions are not blocked — they're valid but must go to human_review.
    # We add a condition so the reviewer knows the penalty applies.
    if action in informational_actions:
        return RuleResult(
            passed=True,
            rule_number=7,
            rule_name="Early Withdrawal Penalty Check",
            conditions=[
                f"Pre-59½ hardship distribution (participant age: {age:.1f}). "
                f"10% early withdrawal penalty (IRC § 72(t)) will apply unless an exception is confirmed by human reviewer."
            ],
        )

    # in_service_distribution and separation_distribution without a valid exception are blocked.
    return RuleResult(
        passed=False,
        rule_number=7,
        rule_name="Early Withdrawal Penalty Check",
        denial_code=DenialCode.early_withdrawal_penalty_applies,
        denial_reason=(
            f"Distribution before age 59½ (participant age: {age:.1f}) is subject to a "
            f"10% early withdrawal penalty under IRC § 72(t). "
            f"Provide a valid penalty_exception in the payload, or route to human review."
        ),
        erisa_citation="IRC § 72(t)",
        master_ref_section="§5.3",
    )


# ---------------------------------------------------------------------------
# Rule 8 — Anti-Alienation Check
# ERISA § 206(d) / IRC § 401(a)(13) — Master Ref §8.2
# ---------------------------------------------------------------------------

def rule_08_anti_alienation(
    action: ActionType,
    payload: dict[str, Any],
) -> RuleResult:
    # Block any transaction that pledges the account as collateral.
    pledges_as_collateral = payload.get("pledges_as_collateral", False)

    if pledges_as_collateral and action != ActionType.loan_initiation:
        return RuleResult(
            passed=False,
            rule_number=8,
            rule_name="Anti-Alienation Check",
            denial_code=DenialCode.anti_alienation_violation,
            denial_reason=(
                "Plan benefits may not be assigned, alienated, or pledged as collateral "
                "except for permissible plan loans (IRC § 72(p)), QDROs, or federal tax levies."
            ),
            erisa_citation="ERISA § 206(d) / IRC § 401(a)(13)",
            master_ref_section="§8.2",
        )

    return RuleResult(passed=True, rule_number=8, rule_name="Anti-Alienation Check")


# ---------------------------------------------------------------------------
# Rule 9 — Prohibited Transaction Check
# ERISA § 406 / IRC § 4975 — Master Ref §6.3, §6.4
# ---------------------------------------------------------------------------

def rule_09_prohibited_transaction(
    principal_type: PrincipalType,
    action: ActionType,
    payload: dict[str, Any],
) -> RuleResult:
    is_party_in_interest = payload.get("counterparty_is_party_in_interest", False)
    is_employer_securities = payload.get("involves_employer_securities", False)
    employer_securities_pct = Decimal(str(payload.get("employer_securities_pct", 0)))

    if is_party_in_interest and action not in {ActionType.loan_initiation, ActionType.rmd}:
        return RuleResult(
            passed=False,
            rule_number=9,
            rule_name="Prohibited Transaction Check",
            denial_code=DenialCode.prohibited_transaction,
            denial_reason=(
                "This transaction involves a party-in-interest. "
                "The transaction must be covered by a statutory or DOL exemption."
            ),
            erisa_citation="ERISA § 406 / IRC § 4975",
            master_ref_section="§6.3",
        )

    if is_employer_securities and employer_securities_pct > Decimal("0.10"):
        return RuleResult(
            passed=False,
            rule_number=9,
            rule_name="Prohibited Transaction Check",
            denial_code=DenialCode.prohibited_transaction,
            denial_reason=(
                f"Employer securities would represent {employer_securities_pct*100:.1f}% of plan assets, "
                f"exceeding the 10% limit under ERISA § 406."
            ),
            erisa_citation="ERISA § 406 / IRC § 4975",
            master_ref_section="§6.3",
        )

    # Investment advisor actions: verify PTE 2020-02 applicability
    if principal_type == PrincipalType.investment_advisor:
        if action in {ActionType.hardship_distribution, ActionType.separation_distribution}:
            pte_applies = payload.get("pte_2020_02_confirmed", False)
            if not pte_applies:
                return RuleResult(
                    passed=False,
                    rule_number=9,
                    rule_name="Prohibited Transaction Check",
                    denial_code=DenialCode.prohibited_transaction,
                    denial_reason=(
                        "Investment advisor rollover/distribution recommendations require PTE 2020-02 "
                        "compliance confirmation. Set pte_2020_02_confirmed=True in the payload."
                    ),
                    erisa_citation="ERISA § 406 / DOL PTE 2020-02",
                    master_ref_section="§6.4",
                )

    return RuleResult(passed=True, rule_number=9, rule_name="Prohibited Transaction Check")


# ---------------------------------------------------------------------------
# Rule 10 — ERISA § 404 Prudent Expert and Loyalty
# ERISA § 404 — Master Ref §6.2
# ---------------------------------------------------------------------------

def rule_10_prudent_expert_loyalty(
    action: ActionType,
    payload: dict[str, Any],
) -> RuleResult:
    # High-stakes irreversible transactions require an explicit acknowledgment.
    high_stakes = {
        ActionType.hardship_distribution,
        ActionType.in_service_distribution,
        ActionType.separation_distribution,
        ActionType.beneficiary_update,
        ActionType.qdro,
        ActionType.rmd,
    }

    if action not in high_stakes:
        return RuleResult(passed=True, rule_number=10, rule_name="Prudent Expert and Loyalty")

    # These transactions are not blocked outright but always require human_review.
    # Rule 10 passes and contributes a condition; Rule 12 will assign human_review.
    return RuleResult(
        passed=True,
        rule_number=10,
        rule_name="Prudent Expert and Loyalty",
        conditions=[
            "High-stakes irreversible transaction. ERISA § 404 prudent expert and loyalty review required."
        ],
    )


# ---------------------------------------------------------------------------
# Rule 11 — RMD Failure Prevention
# IRC § 401(a)(9) — Master Ref §5.2
# ---------------------------------------------------------------------------

def rule_11_rmd_failure_prevention(
    participant: ParticipantRecord,
    action: ActionType,
    payload: dict[str, Any],
) -> RuleResult:
    # Only relevant for distributions of participants who have an active RMD obligation.
    if not participant.rmd_required or not participant.rmd_amount_current_year:
        return RuleResult(passed=True, rule_number=11, rule_name="RMD Failure Prevention")

    # If it's a distribution action, verify it won't leave an RMD shortfall.
    distribution_actions = {
        ActionType.in_service_distribution,
        ActionType.separation_distribution,
        ActionType.hardship_distribution,
    }

    if action not in distribution_actions:
        return RuleResult(passed=True, rule_number=11, rule_name="RMD Failure Prevention")

    rmd_satisfied = payload.get("rmd_satisfied_for_year", False)
    if not rmd_satisfied:
        return RuleResult(
            passed=False,
            rule_number=11,
            rule_name="RMD Failure Prevention",
            denial_code=DenialCode.rmd_shortfall_risk,
            denial_reason=(
                f"Participant has an outstanding RMD of ${participant.rmd_amount_current_year:,.0f} "
                f"for the current plan year. Confirm rmd_satisfied_for_year=True before processing "
                f"additional distributions."
            ),
            erisa_citation="IRC § 401(a)(9)",
            master_ref_section="§5.2",
        )

    return RuleResult(passed=True, rule_number=11, rule_name="RMD Failure Prevention")


# ---------------------------------------------------------------------------
# Rule 12 — Autonomy Level Assignment
# Master Ref §6.2 (ERISA § 404), §5.x
# ---------------------------------------------------------------------------

# Transactions that always require human review regardless of other rule outcomes.
_ALWAYS_HUMAN_REVIEW = {
    ActionType.hardship_distribution,
    ActionType.in_service_distribution,
    ActionType.separation_distribution,
    ActionType.beneficiary_update,
    ActionType.qdro,
    ActionType.rmd,
}

# Transactions that require participant confirmation before final execution.
_ALWAYS_SUPERVISED = {
    ActionType.loan_initiation,
}

# Transactions that can execute immediately.
_ALWAYS_FULL = {
    ActionType.deferral_change,         # but see: deferral-to-zero is supervised
    ActionType.investment_reallocation,
    ActionType.address_update,          # administrative, no tax/legal consequence — PAAP §3.3
}


def rule_12_autonomy_level(
    action: ActionType,
    payload: dict[str, Any],
    accumulated_conditions: list[str],
) -> RuleResult:
    if action in _ALWAYS_HUMAN_REVIEW:
        level = AutonomyLevel.human_review
    elif action in _ALWAYS_SUPERVISED:
        level = AutonomyLevel.supervised
    elif action == ActionType.deferral_change:
        # Reducing deferral to 0% is supervised — confirm opt-out intent.
        new_pct = float(
            payload["deferral_pct"] if "deferral_pct" in payload
            else payload.get("new_deferral_pct", 1.0)
        )
        level = AutonomyLevel.supervised if new_pct == 0.0 else AutonomyLevel.full
    else:
        level = AutonomyLevel.full

    return RuleResult(
        passed=True,
        rule_number=12,
        rule_name="Autonomy Level Assignment",
        autonomy_level=level,
        conditions=accumulated_conditions,
    )


# ---------------------------------------------------------------------------
# Orchestrator — run all 12 rules in order
# ---------------------------------------------------------------------------

def run_compliance_check(
    agent_id: str,
    principal_type: PrincipalType,
    participant: ParticipantRecord,
    plan: PlanRecord,
    action: ActionType,
    payload: dict[str, Any],
) -> RuleResult:
    """
    Evaluate all 12 FAP rules in order.
    Returns the first failing RuleResult, or the Rule 12 autonomy assignment if all pass.
    """
    conditions: list[str] = []

    rules = [
        lambda: rule_01_delegation_validity(agent_id, principal_type, action, plan.plan_id),
        lambda: rule_02_blackout_period(plan, action),
        lambda: rule_03_participation_eligibility(participant, plan, action),
        lambda: rule_04_vesting_enforcement(participant, plan, action, payload),
        lambda: rule_05_contribution_limits(participant, action, payload),
        lambda: rule_06_plan_rules(participant, plan, action, payload),
        lambda: rule_07_early_withdrawal_penalty(participant, action, payload),
        lambda: rule_08_anti_alienation(action, payload),
        lambda: rule_09_prohibited_transaction(principal_type, action, payload),
        lambda: rule_10_prudent_expert_loyalty(action, payload),
        lambda: rule_11_rmd_failure_prevention(participant, action, payload),
    ]

    for rule_fn in rules:
        result = rule_fn()
        if not result.passed:
            return result
        # Collect soft conditions from passing rules
        conditions.extend(result.conditions)

    return rule_12_autonomy_level(action, payload, conditions)
