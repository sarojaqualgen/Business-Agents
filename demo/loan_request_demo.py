"""
Loan Request Demo — touches all three agents (PLAP → FAP → PAAP).

Run from the project root:
    python demo/loan_request_demo.py

Shows:
  Scenario A: $20,000 loan on $80k vested balance → APPROVED (supervised)
  Scenario B: $50,000 loan on $80k vested balance → BLOCKED (LOAN_CAP_EXCEEDED)
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from decimal import Decimal

from agents.fap.agent import authorize
from agents.fap.models import ActionType, AuthorizationApproved, AuthorizationDenied, PrincipalType
from data.plans import get_plan, get_capabilities
from data.participants import get_participant


def _divider(title: str) -> None:
    print(f"\n{'='*60}")
    print(f"  {title}")
    print('='*60)


def run_scenario(
    label: str,
    participant_id: str,
    plan_id: str,
    agent_id: str,
    loan_amount: Decimal,
    repayment_years: int = 5,
    purpose: str = "general",
) -> None:
    _divider(label)

    # Step 1: PLAP — confirm plan allows loans and is not in blackout
    print(f"\n[PLAP] Checking plan capabilities for {plan_id}...")
    plan = get_plan(plan_id)
    if not plan:
        print(f"  ERROR: Plan {plan_id} not found.")
        return

    capabilities = get_capabilities(plan_id)
    print(f"  loan_initiation permitted: {capabilities.capabilities['loan_initiation']}")
    print(f"  blackout active:           {plan.blackout_status.is_active}")
    print(f"  max loan % of vested:      {plan.loan_policy.max_loan_pct_of_vested * 100:.0f}%")
    print(f"  max loan amount (IRC cap): ${plan.loan_policy.max_loan_amount:,}")

    # Step 2: PAAP — read participant data
    print(f"\n[PAAP] Fetching participant data for {participant_id}...")
    participant = get_participant(participant_id)
    if not participant:
        print(f"  ERROR: Participant {participant_id} not found.")
        return

    print(f"  vested balance:            ${participant.vested_balance:,.2f}")
    print(f"  outstanding loans:         {len(participant.outstanding_loans)}")
    print(f"  max additional loan:       ${participant.max_additional_loan_amount:,.2f}")

    # Step 3: FAP — request authorization
    print(f"\n[FAP] Requesting authorization for ${loan_amount:,.0f} loan...")
    payload = {
        "amount": str(loan_amount),
        "repayment_years": repayment_years,
        "purpose": purpose,
    }

    response = authorize(
        agent_id=agent_id,
        principal_type=PrincipalType.participant,
        participant=participant,
        plan=plan,
        action=ActionType.loan_initiation,
        payload=payload,
    )

    if isinstance(response, AuthorizationApproved):
        print(f"\n  ✓ AUTHORIZED")
        print(f"  autonomy_level:  {response.autonomy_level.value}")
        print(f"  token_expires:   {response.token_expires_at}")
        print(f"  audit_id:        {response.audit_id}")
        if response.conditions:
            print(f"  conditions:")
            for c in response.conditions:
                print(f"    - {c}")

        # Step 4: PAAP would execute the loan (simulated)
        print(f"\n[PAAP] Autonomy level = '{response.autonomy_level.value}'")
        if response.autonomy_level.value == "supervised":
            print("  → Surfacing loan confirmation to participant before final execution.")
            print("  → Participant must confirm before PAAP executes the loan.")
        elif response.autonomy_level.value == "full":
            print("  → Executing loan immediately.")

    elif isinstance(response, AuthorizationDenied):
        print(f"\n  ✗ DENIED")
        print(f"  denial_code:     {response.denial_code.value}")
        print(f"  denial_reason:   {response.denial_reason}")
        print(f"  erisa_citation:  {response.erisa_citation}")
        print(f"  master_ref:      {response.master_ref_section}")
        print(f"  audit_id:        {response.audit_id}")
        print(f"\n[PAAP] No token issued — transaction blocked. No execution.")


def main() -> None:
    print("\nAldergate Agentic 401(k) — Loan Request Demo")
    print("PLAP → FAP → PAAP interaction")

    # Scenario A: Amara Osei — $20k on $85k vested → APPROVED (supervised)
    run_scenario(
        label="Scenario A: Amara Osei — $20,000 loan (Capital One, should be APPROVED)",
        participant_id="PART-008",
        plan_id="PLAN-003",
        agent_id="AGENT-PARTICIPANT-001",
        loan_amount=Decimal("20000"),
    )

    # Scenario B: Amara Osei — $50k exceeds 50% of $85k = $42,500 cap → BLOCKED
    run_scenario(
        label="Scenario B: Amara Osei — $50,000 loan (should be BLOCKED — LOAN_CAP_EXCEEDED)",
        participant_id="PART-008",
        plan_id="PLAN-003",
        agent_id="AGENT-PARTICIPANT-001",
        loan_amount=Decimal("50000"),
    )

    # Scenario C: Daniela Reyes — $30k but existing $25k loan caps additional to $25k → BLOCKED
    run_scenario(
        label="Scenario C: Daniela Reyes — $30,000 loan (existing $25k loan, should be BLOCKED — LOAN_CAP_EXCEEDED)",
        participant_id="PART-009",
        plan_id="PLAN-003",
        agent_id="AGENT-PARTICIPANT-001",
        loan_amount=Decimal("30000"),
    )

    print(f"\n{'='*60}")
    print("  Demo complete.")
    print('='*60)


if __name__ == "__main__":
    main()
