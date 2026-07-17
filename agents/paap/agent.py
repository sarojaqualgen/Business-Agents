"""
PAAP Agent — Participant Agent Protocol.

Answers the question: "What can this participant do — and executes it."

Three-layer write flow (per ERISA design):
  1. PAAP calls PLAP  — does this plan support this transaction?
  2. PAAP calls FAP   — is this participant authorized? (issues JWT)
  3. PAAP executes    — writes to PostgreSQL for full-autonomy actions.

Supervised and human_review outcomes are returned to the caller
for routing — PAAP never auto-executes those.

Security invariants enforced by this module:
  - Raw SSN never returned (only ssn_hash).
  - Date of birth never returned externally.
  - Marital status never returned.
  - Full account balance returned only in participant summary (needed for
    participant's own benefit statement); loan_headroom endpoint returns
    only the IRC §72(p) headroom figure, not the full balance.
"""

from typing import Any

from agents.plap.agent import PlanNotFound, query_capabilities
from agents.fap.agent import authorize
from agents.fap.models import ActionType, PrincipalType
from agents.paap.models import ParticipantRecord
from data.db import get_participant


class ParticipantNotFound(Exception):
    pass


class PlanDoesNotSupportAction(Exception):
    pass


class UnauthorizedByFAP(Exception):
    def __init__(self, denial_reason: str, denial_code: str):
        self.denial_reason = denial_reason
        self.denial_code = denial_code
        super().__init__(denial_reason)


def _load(participant_id: str) -> ParticipantRecord:
    p = get_participant(participant_id)
    if p is None:
        raise ParticipantNotFound(f"Participant '{participant_id}' not found.")
    return p


def get_participant_plan_id(participant_id: str) -> str:
    """Return the plan_id for a participant. Raises ParticipantNotFound if not found."""
    return _load(participant_id).plan_id


# ---------------------------------------------------------------------------
# Read operations — no FAP token required
# ---------------------------------------------------------------------------

def get_participant_summary(participant_id: str) -> dict:
    """
    Benefit statement snapshot. Returns fields safe for participant view.
    Never exposes raw SSN, date of birth, or marital status.
    """
    p = _load(participant_id)
    return {
        "participant_id":             p.participant_id,
        "plan_id":                    p.plan_id,
        "ssn_hash":                   p.ssn_hash,
        "employment_status":          p.employment_status.value,
        "hire_date":                  p.hire_date,
        "eligibility_date":           p.eligibility_date,
        "years_of_vesting_service":   p.years_of_vesting_service,
        "vesting_percentage":         p.vesting_percentage,
        "total_balance":              float(p.total_balance),
        "vested_balance":             float(p.vested_balance),
        "current_deferral_pct":       p.current_deferral_pct,
        "deferral_type":              p.deferral_type.value,
        "investment_elections": [
            {"fund_id": e.fund_id, "allocation_pct": e.allocation_pct}
            for e in p.investment_elections
        ],
        "employee_contributions_ytd": float(p.employee_contributions_ytd),
        "employer_contributions_ytd": float(p.employer_contributions_ytd),
        "outstanding_loan_count":     len(p.outstanding_loans),
        "rmd_required":               p.rmd_required,
        "is_hce":                     p.is_hce,
        "age_50_or_older":            p.age_50_or_older,
        "age_60_to_63":               p.age_60_to_63,
    }


def get_vesting_info(participant_id: str) -> dict:
    p = _load(participant_id)
    return {
        "participant_id":           p.participant_id,
        "plan_id":                  p.plan_id,
        "years_of_vesting_service": p.years_of_vesting_service,
        "vesting_percentage":       p.vesting_percentage,
        "vested_balance":           float(p.vested_balance),
        "total_balance":            float(p.total_balance),
        "break_in_service":         p.break_in_service,
        "userra_military_leave":    p.userra_military_leave,
    }


def get_loan_headroom(participant_id: str) -> dict:
    """
    IRC §72(p): returns only the maximum additional loan amount.
    Full vested balance is not returned here.
    """
    p = _load(participant_id)
    return {
        "participant_id":         p.participant_id,
        "plan_id":                p.plan_id,
        "loan_headroom":          float(p.max_additional_loan_amount),
        "outstanding_loan_count": len(p.outstanding_loans),
        "outstanding_loans": [
            {
                "loan_id":             loan.loan_id,
                "outstanding_balance": float(loan.outstanding_balance),
                "maturity_date":       loan.maturity_date,
            }
            for loan in p.outstanding_loans
        ],
    }


def get_rmd_info(participant_id: str) -> dict:
    p = _load(participant_id)
    return {
        "participant_id": p.participant_id,
        "plan_id":        p.plan_id,
        "rmd_required":   p.rmd_required,
        "rmd_amount":     float(p.rmd_amount_current_year) if p.rmd_amount_current_year else None,
        "rmd_due_date":   p.rmd_due_date,
    }


def get_distribution_options(participant_id: str) -> dict:
    """Return available distribution types based on participant age, status, and plan rules."""
    p = _load(participant_id)
    try:
        caps = query_capabilities(p.plan_id)["capabilities"]
    except PlanNotFound:
        caps = {}

    return {
        "participant_id":    p.participant_id,
        "plan_id":           p.plan_id,
        "employment_status": p.employment_status.value,
        "available_options": {
            "in_service_59_5":   caps.get("in_service_distribution", False),
            "hardship":          caps.get("hardship_distribution", False),
            "separation":        p.employment_status.value in ("terminated", "retired"),
            "rmd":               p.rmd_required,
            "direct_rollover":   caps.get("direct_rollover_out", False),
        },
    }


# ---------------------------------------------------------------------------
# Write operations — PAAP → PLAP → FAP → execute
# ---------------------------------------------------------------------------

_ACTION_TO_CAP = {
    "loan_initiation":         "loan_initiation",
    "hardship_distribution":   "hardship_distribution",
    "in_service_distribution": "in_service_distribution",
    "separation_distribution": "separation_distribution",
    "direct_rollover_out":     "direct_rollover_out",
    "rollover_in":             "rollover_in",
}


def execute(
    participant_id: str,
    agent_id: str,
    action: str,
    payload: dict[str, Any],
) -> dict:
    """
    PAAP three-layer write flow.

    PAAP owns participant data access — callers never pass plan_id directly;
    PAAP loads the participant and derives plan_id internally.

    Layer 1 — PLAP: does this plan allow this action?
    Layer 2 — FAP:  is this participant authorized? (runs 12 ERISA rules)
    Layer 3 — Execute: write to PostgreSQL for full-autonomy actions only.

    Returns autonomy_level and fap_token (non-null for supervised/human_review).
    Supervised and human_review results are NOT auto-executed — the caller routes them.
    Raises UnauthorizedByFAP on any FAP denial.
    """
    # Load participant — PAAP is the sole gatekeeper for participant data
    participant = _load(participant_id)
    plan_id = participant.plan_id

    # Layer 1 — PLAP check
    try:
        caps = query_capabilities(plan_id)["capabilities"]
    except PlanNotFound as e:
        raise PlanDoesNotSupportAction(str(e))

    cap_key = _ACTION_TO_CAP.get(action)
    if cap_key and not caps.get(cap_key, True):
        raise PlanDoesNotSupportAction(
            f"Plan '{plan_id}' does not support '{action}'."
        )

    # Layer 2 — FAP authorization
    try:
        action_type = ActionType(action)
    except ValueError:
        action_type = None

    autonomy_level = "full"
    fap_result = None
    if action_type is not None:
        from data.db import get_plan
        plan = get_plan(plan_id)
        if plan is None:
            raise PlanNotFound(f"Plan '{plan_id}' not found.")

        fap_result = authorize(
            agent_id=agent_id,
            principal_type=PrincipalType.participant,
            participant=participant,
            plan=plan,
            action=action_type,
            payload=payload,
        )
        if not fap_result.authorized:
            raise UnauthorizedByFAP(
                denial_reason=fap_result.denial_reason,
                denial_code=fap_result.denial_code,
            )
        autonomy_level = fap_result.autonomy_level.value if fap_result.autonomy_level else "full"

    # Layer 3 — Execute (full autonomy only)
    executed = False
    if autonomy_level == "full":
        _execute_write(participant_id, plan_id, action, payload)
        executed = True

    return {
        "participant_id": participant_id,
        "plan_id":        plan_id,
        "action":         action,
        "autonomy_level": autonomy_level,
        "executed":       executed,
        "fap_token":      fap_result.token if (fap_result is not None and not executed) else None,
        "message": (
            "Transaction executed successfully."
            if executed
            else (
                "Awaiting participant confirmation."
                if autonomy_level == "supervised"
                else "Queued for sponsor review."
            )
        ),
    }


def execute_confirmed(
    participant_id: str,
    action: str,
    payload: dict,
    fap_token: str,
) -> dict:
    """
    Execute a write for a transaction whose FAP token was already issued earlier
    (confirm / disburse flow).

    The 12 ERISA rules ran when the token was issued. This only re-validates
    the token cryptographically — single-use, not tampered, correct participant
    and action — then delegates the DB write to _execute_write().

    Raises UnauthorizedByFAP if the token is invalid or already consumed.
    """
    from agents.fap.tokens import validate_token

    participant = _load(participant_id)
    plan_id = participant.plan_id

    valid, reason = validate_token(
        token_str=fap_token,
        expected_action=action,
        expected_participant_id=participant_id,
        expected_payload=payload,
    )
    if not valid:
        raise UnauthorizedByFAP(denial_reason=reason, denial_code="TOKEN_INVALID")

    _execute_write(participant_id, plan_id, action, payload)
    return {
        "participant_id": participant_id,
        "plan_id":        plan_id,
        "action":         action,
        "executed":       True,
        "status":         "executed",
        "message":        "Transaction executed successfully.",
    }


def _execute_write(participant_id: str, plan_id: str, action: str, payload: dict) -> None:
    """Write to PostgreSQL. Called for full-autonomy actions and by execute_confirmed()."""
    from decimal import Decimal
    from data import db

    if action == "deferral_change":
        pct = float(payload.get("new_deferral_pct", payload.get("deferral_pct", 0)))
        d_type = payload.get("deferral_type", "pre_tax")
        db.update_deferral(participant_id, pct, d_type)
        db.record_transaction(
            participant_id=participant_id,
            plan_id=plan_id,
            action=action,
            payload=payload,
            autonomy_level="full",
        )

    elif action == "investment_reallocation":
        elections = payload.get("elections", [])
        if elections:
            db.update_investment_elections(participant_id, plan_id, elections)
            db.record_transaction(
                participant_id=participant_id,
                plan_id=plan_id,
                action=action,
                payload=payload,
                autonomy_level="full",
            )

    elif action == "loan_initiation":
        amount = Decimal(str(payload.get("amount", 0)))
        repayment_years = int(payload.get("repayment_years", 5))
        db.decrement_vested_balance(participant_id=participant_id, amount=amount)
        db.create_loan_record(
            participant_id=participant_id,
            plan_id=plan_id,
            amount=amount,
            repayment_years=repayment_years,
        )
        db.record_transaction(
            participant_id=participant_id,
            plan_id=plan_id,
            action=action,
            amount=amount,
            payload=payload,
            autonomy_level="supervised",
        )

    # hardship_distribution, separation_distribution, beneficiary_update, qdro
    # go to human_review — sponsor approves, then execute_confirmed() is called here.
