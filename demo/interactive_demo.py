"""
Aldergate — Interactive Demo with Live Backend Trace
Run: python demo/interactive_demo.py
"""

import sys
import os
import time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from decimal import Decimal

from agents.fap.agent import authorize
from agents.fap.models import ActionType, AuthorizationApproved, AuthorizationDenied, PrincipalType
from agents.fap.compliance import (
    rule_01_delegation_validity, rule_02_blackout_period,
    rule_03_participation_eligibility, rule_04_vesting_enforcement,
    rule_05_contribution_limits, rule_06_plan_rules,
    rule_07_early_withdrawal_penalty, rule_08_anti_alienation,
    rule_09_prohibited_transaction, rule_10_prudent_expert_loyalty,
    rule_11_rmd_failure_prevention, rule_12_autonomy_level,
)
from data.plans import get_plan
from data.participants import get_participant

# ── ANSI colors ───────────────────────────────────────────────────────────────
G   = "\033[92m"
R   = "\033[91m"
Y   = "\033[93m"
B   = "\033[94m"
C   = "\033[96m"
W   = "\033[97m"
DIM = "\033[2m"
RST = "\033[0m"

def hr(char="─", n=64): print(f"{DIM}{char * n}{RST}")
def header(t): print(); hr("═"); print(f"{W}  {t}{RST}"); hr("═")
def section(t): print(f"\n{C}┌─ {t}{RST}"); hr()

def pause(s=0.35): time.sleep(s)

# ── Data ──────────────────────────────────────────────────────────────────────
PARTICIPANTS = {
    "1": ("PART-008", "Amara Osei",     "Age 36 · $85,000 vested · No loans · 5yr service · Capital One"),
    "2": ("PART-006", "Gabriel Stone",  "Age 61 · $210,000 vested · HCE · Catch-up eligible · Capital One"),
    "3": ("PART-009", "Daniela Reyes",  "Age 41 · $100,000 vested · Existing $25k loan · Capital One"),
    "4": ("PART-007", "Yuki Tanaka",    "Age 31 · $38,000 vested · 1.5yr service · Cliff NOT met · Prudential"),
}

PLANS = {
    "1": ("PLAN-003", "Capital One Associate Savings Plan",   "Safe harbor · Immediate eligibility · Fidelity"),
    "2": ("PLAN-004", "Prudential Employee Savings Plan",     "1yr eligibility wait · 3yr vesting cliff · Empower"),
}

ACTIONS = {
    "1": (ActionType.loan_initiation,         "Loan Request",             "Borrow from your own 401(k) balance"),
    "2": (ActionType.deferral_change,         "Deferral Change",          "Change your paycheck contribution %"),
    "3": (ActionType.hardship_distribution,   "Hardship Distribution",    "Emergency withdrawal from account"),
    "4": (ActionType.separation_distribution, "Separation Distribution",  "Take money out after leaving employer"),
    "5": (ActionType.investment_reallocation, "Investment Reallocation",  "Rebalance fund allocations"),
}

# ── Pickers ───────────────────────────────────────────────────────────────────
def pick(label, options):
    for k, v in options.items():
        name = v[1]
        note = v[2]
        print(f"  {Y}{k}{RST}  {W}{name}{RST}")
        print(f"     {DIM}{note}{RST}")
    print()
    while True:
        c = input(f"  {B}Select [{'/'.join(options)}]: {RST}").strip()
        if c in options:
            return c

def pick_participant():
    section("STEP 1  ·  Select Participant")
    c = pick("participant", PARTICIPANTS)
    pid, name, _ = PARTICIPANTS[c]
    return pid, name

def pick_plan():
    section("STEP 2  ·  Select Plan")
    c = pick("plan", PLANS)
    pid, name, _ = PLANS[c]
    return pid, name

def pick_action():
    section("STEP 3  ·  Select Action")
    c = pick("action", ACTIONS)
    action, label, _ = ACTIONS[c]
    return action, label

def build_payload(action, participant_id):
    p = get_participant(participant_id)

    if action == ActionType.loan_initiation:
        section("STEP 4  ·  Loan Details")
        print(f"  {DIM}Vested balance    ${p.vested_balance:,.2f}{RST}")
        print(f"  {DIM}Max loan allowed  ${p.max_additional_loan_amount:,.2f}{RST}\n")
        amount  = input(f"  {B}Loan amount ($): {RST}$").strip()
        years   = input(f"  {B}Repayment years [1-15]: {RST}").strip() or "5"
        purpose = input(f"  {B}Purpose [general / primary_residence]: {RST}").strip() or "general"
        return {"amount": amount, "repayment_years": int(years), "purpose": purpose}

    if action == ActionType.deferral_change:
        section("STEP 4  ·  Deferral Details")
        print(f"  {DIM}Current deferral  {p.current_deferral_pct*100:.1f}%{RST}")
        print(f"  {DIM}Compensation YTD  ${p.compensation_ytd:,.2f}{RST}\n")
        pct = input(f"  {B}New deferral % (e.g. 6 for 6%): {RST}").strip()
        return {"deferral_pct": float(pct) / 100}

    if action == ActionType.hardship_distribution:
        section("STEP 4  ·  Hardship Details")
        exps = ["medical","tuition","primary_home_purchase",
                "prevent_eviction","funeral","casualty_loss","FEMA_disaster"]
        for i, e in enumerate(exps, 1): print(f"  {Y}{i}{RST}  {e}")
        print()
        c = input(f"  {B}Expense type [1-7]: {RST}").strip()
        exp = exps[int(c)-1] if c.isdigit() and 1 <= int(c) <= 7 else "medical"
        amt = input(f"  {B}Amount ($): {RST}$").strip()
        return {"qualifying_expense_type": exp, "amount": amt}

    if action == ActionType.separation_distribution:
        section("STEP 4  ·  Separation Details")
        print(f"  {DIM}Employment status: {p.employment_status}{RST}\n")
        n = input(f"  {B}Was 402(f) rollover notice sent? [y/n]: {RST}").strip().lower()
        return {"rollover_402f_notice_confirmed": n == "y"}

    return {}

# ── Live backend trace ────────────────────────────────────────────────────────
RULE_NAMES = [
    "Delegation Validity",
    "Blackout Period Check",
    "Participation & Eligibility",
    "Vesting Enforcement",
    "Contribution Limits",
    "Plan Rule Enforcement",
    "Early Withdrawal Penalty",
    "Anti-Alienation",
    "Prohibited Transaction",
    "Prudent Expert & Loyalty",
    "RMD Failure Prevention",
]

RULE_CITATIONS = [
    "ERISA § 404",
    "ERISA § 101(i)",
    "ERISA § 202 / IRC § 410(a)",
    "ERISA § 203 / IRC § 411",
    "IRC §§ 402(g), 414(v), 415(c)",
    "IRC § 72(p) / § 401(k)",
    "IRC § 72(t)",
    "ERISA § 206(d)",
    "ERISA § 406 / IRC § 4975",
    "ERISA § 404",
    "IRC § 401(a)(9)",
]


def run_with_trace(participant_id, plan_id, action, payload, participant_name, plan_name, action_label):
    participant = get_participant(participant_id)
    plan        = get_plan(plan_id)

    # ── PLAP ─────────────────────────────────────────────────────────────────
    print()
    hr("─")
    print(f"{C}  PLAP  —  Plan Rules Module{RST}")
    print(f"  {DIM}\"What does this plan allow?\"{RST}")
    hr("─")
    pause(0.3)
    print(f"  {DIM}→ Fetching plan: {plan_name}{RST}")
    pause(0.4)
    print(f"  {G}✓{RST} {DIM}Plan found{RST}")
    print(f"    {DIM}Loans permitted:     {RST}{G if plan.loan_policy.loans_permitted else R}{plan.loan_policy.loans_permitted}{RST}")
    print(f"    {DIM}Blackout active:     {RST}{R if plan.blackout_status.is_active else G}{plan.blackout_status.is_active}{RST}")
    if plan.blackout_status.is_active:
        print(f"    {R}Blackout reason:     {plan.blackout_status.reason}{RST}")
    print(f"    {DIM}Eligibility age:     {RST}{plan.eligibility_age}")
    print(f"    {DIM}Vesting type:        {RST}{plan.match_vesting_schedule.vesting_type.value}")
    if plan.loan_policy.loans_permitted:
        print(f"    {DIM}Max loan % vested:   {RST}{plan.loan_policy.max_loan_pct_of_vested*100:.0f}%")
        print(f"    {DIM}IRC § 72(p) cap:     {RST}$50,000")

    # ── PAAP ─────────────────────────────────────────────────────────────────
    print()
    hr("─")
    print(f"{C}  PAAP  —  Participant Data Module{RST}")
    print(f"  {DIM}\"What does this participant's account look like?\"{RST}")
    hr("─")
    pause(0.3)
    print(f"  {DIM}→ Fetching participant: {participant_name}{RST}")
    pause(0.4)
    print(f"  {G}✓{RST} {DIM}Account found{RST}")
    print(f"    {DIM}Vested balance:      {RST}${participant.vested_balance:,.2f}")
    print(f"    {DIM}Total balance:       {RST}${participant.total_balance:,.2f}")
    print(f"    {DIM}Outstanding loans:   {RST}{len(participant.outstanding_loans)}")
    if action == ActionType.loan_initiation:
        print(f"    {DIM}Max additional loan: {RST}${participant.max_additional_loan_amount:,.2f}  {DIM}(IRC § 72(p) calc){RST}")
    print(f"    {DIM}Employment status:   {RST}{participant.employment_status.value}")
    print(f"    {DIM}Years of service:    {RST}{participant.years_of_vesting_service:.1f}")
    print(f"    {DIM}HCE:                 {RST}{participant.is_hce}")

    # ── FAP ──────────────────────────────────────────────────────────────────
    print()
    hr("─")
    print(f"{C}  FAP  —  Compliance Engine{RST}")
    print(f"  {DIM}\"Is this authorized and ERISA-compliant?\"{RST}")
    print(f"  {DIM}Running 12 rules in sequence. First failure = DENIED.{RST}")
    hr("─")
    pause(0.4)

    rule_fns = [
        lambda: rule_01_delegation_validity("AGENT-PARTICIPANT-001", PrincipalType.participant, action, plan.plan_id),
        lambda: rule_02_blackout_period(plan, action),
        lambda: rule_03_participation_eligibility(participant, plan, action),
        lambda: rule_04_vesting_enforcement(participant, plan, action, payload),
        lambda: rule_05_contribution_limits(participant, action, payload),
        lambda: rule_06_plan_rules(participant, plan, action, payload),
        lambda: rule_07_early_withdrawal_penalty(participant, action, payload),
        lambda: rule_08_anti_alienation(action, payload),
        lambda: rule_09_prohibited_transaction(PrincipalType.participant, action, payload),
        lambda: rule_10_prudent_expert_loyalty(action, payload),
        lambda: rule_11_rmd_failure_prevention(participant, action, payload),
    ]

    conditions = []
    final_result = None

    for i, rule_fn in enumerate(rule_fns):
        num  = f"{i+1:02d}"
        name = RULE_NAMES[i]
        cite = RULE_CITATIONS[i]
        pause(0.25)
        result = rule_fn()

        if result.passed:
            cond_note = f"  {Y}+ condition{RST}" if result.conditions else ""
            print(f"  {G}✓{RST}  Rule {num}  {W}{name}{RST}  {DIM}{cite}{RST}{cond_note}")
            conditions.extend(result.conditions)
        else:
            print(f"  {R}✗{RST}  Rule {num}  {W}{name}{RST}  {DIM}{cite}{RST}")
            print(f"       {R}→ {result.denial_code.value}{RST}")
            print(f"       {DIM}{result.denial_reason}{RST}")
            final_result = result
            print(f"\n  {DIM}Remaining rules skipped. Fail-fast.{RST}")
            break
    else:
        # all rules passed — run Rule 12
        pause(0.25)
        r12 = rule_12_autonomy_level(action, payload, conditions)
        level = r12.autonomy_level.value
        color = G if level == "full" else Y if level == "supervised" else R
        print(f"  {G}✓{RST}  Rule 12  {W}Autonomy Level Assignment{RST}")
        print(f"       {color}→ {level}{RST}")
        final_result = None

    # ── Token & audit ────────────────────────────────────────────────────────
    pause(0.3)
    print()
    hr("─")
    print(f"{C}  FAP  —  Token + Audit{RST}")
    hr("─")
    pause(0.3)

    response = authorize(
        agent_id="AGENT-PARTICIPANT-001",
        principal_type=PrincipalType.participant,
        participant=participant,
        plan=plan,
        action=action,
        payload=payload,
    )

    if isinstance(response, AuthorizationApproved):
        print(f"  {G}✓{RST} JWT token issued    {DIM}(scoped · HS256 · single-use · 5min TTL){RST}")
        print(f"  {G}✓{RST} Audit record written  {DIM}outcome=approved{RST}")
        print(f"    {DIM}Audit ID: {response.audit_id}{RST}")
    else:
        print(f"  {R}✗{RST} No token issued")
        print(f"  {G}✓{RST} Audit record written  {DIM}outcome=denied{RST}")
        print(f"    {DIM}Audit ID: {response.audit_id}{RST}")

    # ── Final result ──────────────────────────────────────────────────────────
    print()
    hr("═")
    if isinstance(response, AuthorizationApproved):
        level = response.autonomy_level.value
        print(f"{G}  ✓  AUTHORIZED{RST}  ·  {W}{action_label}{RST}")
        hr()
        if level == "full":
            print(f"  {G}Autonomy: full{RST}  →  PAAP executes immediately, no confirmation needed")
        elif level == "supervised":
            print(f"  {Y}Autonomy: supervised{RST}  →  PAAP surfaces confirmation to participant first")
        else:
            print(f"  {R}Autonomy: human_review{RST}  →  PAAP queues for plan admin before execution")
        if response.conditions:
            print(f"\n  {Y}Conditions flagged:{RST}")
            for c in response.conditions:
                print(f"    {DIM}• {c}{RST}")
    else:
        print(f"{R}  ✗  DENIED{RST}  ·  {W}{action_label}{RST}")
        hr()
        print(f"  {R}Code:      {RST}{response.denial_code.value}")
        print(f"  {W}Reason:    {RST}{response.denial_reason}")
        print(f"  {DIM}Citation:  {response.erisa_citation}{RST}")
        print(f"\n  {DIM}PAAP received no token. Nothing executes.{RST}")
    hr("═")


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    print("\033[2J\033[H", end="")
    header("Aldergate  ·  ERISA 401(k) Compliance Engine Demo")
    print(f"  {DIM}Live compliance trace  ·  PLAP → PAAP → FAP → PAAP{RST}")
    print(f"\n  {DIM}PLAP   Plan Rules Module      — reads what the plan allows{RST}")
    print(f"  {DIM}PAAP   Participant Data Module — reads the participant's account{RST}")
    print(f"  {DIM}FAP    Compliance Engine       — runs 12 ERISA rules, issues token{RST}")
    print(f"  {DIM}PAAP   (executes only with a valid FAP token){RST}")
    print(f"\n  {Y}Phase 3 (not built yet):{RST}")
    print(f"  {DIM}Three CrewAI agents (Intent · Data · Compliance) will sit on top of{RST}")
    print(f"  {DIM}these modules. A participant will type \"I want a loan\" in plain English.{RST}")
    print(f"  {DIM}Claude interprets intent → these modules enforce law.{RST}")
    print(f"  {DIM}Compliance decisions will NEVER be made by AI.{RST}")

    while True:
        participant_id, participant_name = pick_participant()
        plan_id, plan_name               = pick_plan()
        action, action_label             = pick_action()
        payload                          = build_payload(action, participant_id)

        run_with_trace(
            participant_id, plan_id, action, payload,
            participant_name, plan_name, action_label
        )

        print()
        again = input(f"  {B}Try another scenario? [y/n]: {RST}").strip().lower()
        if again != "y":
            print(f"\n  {DIM}Demo complete.{RST}\n")
            break


if __name__ == "__main__":
    main()
