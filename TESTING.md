# Aldergate — Testing Guide

## Overview

The test suite covers the FAP compliance engine (pure Python, no API key needed).
87 tests across all 12 ERISA rules. Every rule has at least one pass case and one fail case.

**No stubs.** Every test exercises real evaluation logic — no mocked rule that always returns approved.

---

## Running Tests

```bash
# From project root, with .venv active
source .venv/bin/activate

# Run everything
pytest tests/ -v

# Run a specific rule class
pytest tests/ -v -k "TestRule05"

# Run and see only failures
pytest tests/ -v --tb=short
```

---

## Test Data — Who the Participants Are

| ID | Name | Plan | Key Characteristic | Tests Best For |
|---|---|---|---|---|
| PART-006 | Gabriel Stone | PLAN-003 | Age 61, HCE ($185k comp), $210k vested, near retirement | SECURE 2.0 Roth catch-up, in-service distribution, catch-up limits |
| PART-007 | Yuki Tanaka | PLAN-004 | Age 31, 1.5yr service, cliff not met on either plan | Vesting enforcement, eligibility blocks |
| PART-008 | Amara Osei | PLAN-003 | Age 36, $85k vested, no loans, 5yr service | Loan approval, deferral, primary demo participant |
| PART-009 | Daniela Reyes | PLAN-003 | Age 41, $100k vested, existing $25k loan | IRC §72(p) loan cap math (max additional = $25k) |

| ID | Plan | Key Characteristic |
|---|---|---|
| PLAN-003 | Capital One Associate Savings Plan | Safe harbor, immediate eligibility (age 18), 2yr cliff vesting, 5yr/10yr loans, up to 2 loans |
| PLAN-004 | Prudential Employee Savings Plan (PESP) | 1yr service wait, 3yr cliff vesting, 5yr/15yr loans, max 1 loan |

**Blackout and no-loan plan variants** are created inline as pytest fixtures (`blackout_plan`, `no_loan_plan`, `no_hardship_plan`) that deep-copy PLAN-003 and mutate the relevant policy field — no separate seeded plan needed.

---

## The 12 Rules — What Each Test Covers

### Rule 1 — Delegation Validity (ERISA § 404)
- Registered active agent passes
- Unknown agent ID → `AGENT_NOT_REGISTERED`
- Inactive agent → `AGENT_NOT_REGISTERED`
- Wrong principal_type → `DELEGATION_SCOPE_EXCEEDED`
- Action outside scope → `DELEGATION_SCOPE_EXCEEDED`
- Plan ID outside scope → `DELEGATION_SCOPE_EXCEEDED`
- Wildcard `"*"` plan ID passes

### Rule 2 — Blackout Period (ERISA § 101(i))
- No blackout → passes
- Write action during active blackout → `BLACKOUT_ACTIVE`
- RMD during blackout → **permitted** (regulatory obligation, cannot block)

### Rule 3 — Participation & Eligibility (ERISA § 202 / IRC § 410(a))
- Eligible participant passes
- Future eligibility date → `ENTRY_DATE_NOT_REACHED`
- Participant under minimum age → `ELIGIBILITY_NOT_MET`
- QDRO/beneficiary not eligibility-gated → passes

### Rule 4 — Vesting Enforcement (ERISA § 203 / IRC § 411)
- Non-distribution actions bypass vesting check
- Fully vested (Amara, 5yr service — exceeds Capital One's 2yr cliff) → passes separation distribution
- 1.5yr participant (Yuki) → `INSUFFICIENT_VESTING` on both plans (below 2yr and 3yr cliffs)
- Employee-deferrals-only source → bypasses employer vesting check

### Rule 5 — Contribution Limits (IRC §§ 402(g), 414(v), 415(c))
- Deferral 6% of $95k ($5,700) → passes
- Deferral exceeding $23k base → `DEFERRAL_LIMIT_EXCEEDED`
- Age 50+ catch-up: combined limit = $23k + $7.5k = $30.5k
- Total annual additions > $69k → `ANNUAL_ADDITIONS_LIMIT_EXCEEDED`
- **SECURE 2.0 Roth catch-up (effective 2026):**
  - Income > $145k, age 50+, deferral > $23k, pre-tax → `ROTH_CATCHUP_REQUIRED`
  - Same participant with `deferral_type=roth` → passes
  - Income < $145k → Roth rule does not apply
  - Not catch-up eligible (under 50) → rule does not apply

### Rule 6 — Plan Rule Enforcement (plan-specific)

**Loan rules:**
- $20k on $85k vested (Amara, PLAN-003) → passes
- Exceeds 50% vested → `LOAN_CAP_EXCEEDED`
- Plan doesn't permit loans → `LOAN_NOT_PERMITTED` (via `no_loan_plan` fixture)
- Existing $25k loan (Daniela) reduces IRS $50k cap → IRC §72(p) math tested
- Term > 5yr general purpose → `LOAN_CAP_EXCEEDED`
- Primary residence 10yr term → passes (Capital One's plan limit)

**Hardship rules:**
- Valid safe harbor expense → passes
- Invalid expense type → `HARDSHIP_CRITERIA_NOT_MET`
- Plan doesn't permit hardship → `HARDSHIP_NOT_PERMITTED`
- Legacy `six_month_contribution_suspension=True` → passes but adds reviewer condition

**In-service distribution:**
- Under 59½ → `IN_SERVICE_AGE_NOT_MET`
- Age 62 → passes

**Separation distribution:**
- Active employee → `SEPARATION_STATUS_INVALID`
- Terminated, no 402(f) notice → `ROLLOVER_NOTICE_NOT_ISSUED`
- Terminated + notice confirmed → passes

**RMD:**
- `rmd_required=False` → `RMD_NOT_YET_REQUIRED`
- Notice not issued → `RMD_NOTICE_NOT_ISSUED`
- Notice confirmed, amount below required → `RMD_AMOUNT_INSUFFICIENT`
- Notice confirmed, sufficient amount → passes

### Rule 7 — Early Withdrawal Penalty (IRC § 72(t))
- Non-distribution → passes
- Age 62 → no penalty
- Age ~46, no exception → `EARLY_WITHDRAWAL_PENALTY_APPLIES`
- `disability` exception → passes
- `sepp_72t` exception → passes
- `separation_age_55` claimed but age < 55 → fails
- SECURE 2.0 `emergency_personal_expense` → passes

### Rule 8 — Anti-Alienation (ERISA § 206(d))
- Normal transaction → passes
- `pledges_as_collateral=True` → `ANTI_ALIENATION_VIOLATION`
- QDRO passes (legal exception)

### Rule 9 — Prohibited Transaction (ERISA § 406)
- Standard participant transaction → passes
- Party-in-interest → `PROHIBITED_TRANSACTION`
- Employer securities > 10% → `PROHIBITED_TRANSACTION`
- Employer securities < 10% → passes
- Advisor distribution without PTE 2020-02 → `PROHIBITED_TRANSACTION`

### Rule 10 — Prudent Expert & Loyalty (ERISA § 404)
- Low-stakes action → passes, no conditions
- Hardship/QDRO/separation → passes, adds reviewer condition

### Rule 11 — RMD Failure Prevention (IRC § 401(a)(9))
- No RMD obligation → passes
- RMD outstanding, `rmd_satisfied_for_year` missing → `RMD_SHORTFALL_RISK`
- `rmd_satisfied_for_year=True` → passes

### Rule 12 — Autonomy Level Assignment
| Action | Autonomy |
|---|---|
| deferral_change (increase) | full |
| deferral_change (to 0%) | supervised |
| investment_reallocation | full |
| address_update | full |
| loan_initiation | supervised |
| hardship_distribution | human_review |
| in_service_distribution | human_review |
| separation_distribution | human_review |
| rmd | human_review |
| beneficiary_update | human_review |
| qdro | human_review |

---

## End-to-End Scenarios (Full 12-Rule Orchestration)

| Scenario | Participant | Action | Expected result |
|---|---|---|---|
| Approved loan | PART-008 Amara | loan $20k | passes, supervised |
| Loan cap exceeded | PART-008 Amara | loan $50k on $85k | fails rule 6 |
| IRC §72(p) existing loan | PART-009 Daniela | loan $30k (cap=$25k) | fails rule 6 |
| Blackout block | PART-008 Amara | loan (`blackout_plan` fixture) | fails rule 2 |
| Unknown agent | any | any | fails rule 1 |
| Deferral increase | PART-008 Amara | 8% pre-tax | passes, full |
| Hardship | PART-008 Amara | medical $5k | passes, human_review |
| SECURE 2.0 catch-up | PART-006 Gabriel | 15% pre-tax (HCE, $185k) | fails rule 5 |
| Address update | PART-008 Amara | address change | passes, full |

---

## Manual CLI Testing (No API Key Needed)

```bash
python -c "
from agents.fap.compliance import run_compliance_check
from agents.fap.models import ActionType, PrincipalType
from data.participants import PART_008
from data.plans import PLAN_003

result = run_compliance_check(
    agent_id='AGENT-PARTICIPANT-001',
    principal_type=PrincipalType.participant,
    participant=PART_008,
    plan=PLAN_003,
    action=ActionType.loan_initiation,
    payload={'amount': '20000', 'repayment_years': 5, 'purpose': 'general'},
)
print('passed:', result.passed)
print('autonomy:', result.autonomy_level)
print('denial:', result.denial_code)
"
```

---

## Adding New Tests

```python
class TestRuleXX:

    def test_passes_SCENARIO(self, participant, plan):
        result = rule_XX_function(participant, plan, ActionType.loan_initiation, {})
        assert result.passed

    def test_fails_SCENARIO(self, participant, plan):
        result = rule_XX_function(participant, plan, ActionType.loan_initiation, {})
        assert not result.passed
        assert result.denial_code == DenialCode.specific_code
```

**Rules:**
- Use fixtures (`participant`, `plan`) — they deep-copy mock data so mutations don't persist
- Always assert the specific `denial_code`, not just `not result.passed`
- Always add both a pass case and a fail case

---

## What Is NOT Covered (Future Phases)

| Area | Reason |
|---|---|
| PostgreSQL write mutations | Phase 6 — reads work; write-back pending |
| SFTP recordkeeper ingestion | Phase 5 — not built yet |
| FastAPI endpoints | Phase 4 — not built yet |
| CrewAI LLM tool calls | Requires API key, not in automated CI |
| USERRA military leave math | Edge case flagged in paap-agent.md |
| Break-in-service < 5yr restoration | Edge case flagged in paap-agent.md |

---

## Current State

```
87 tests — 87 passed — 0 failed
```

Run with: `pytest tests/ -v`  (no API key required — pure Python compliance engine)
