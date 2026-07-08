# Aldergate — CLI Reference Guide

Everything you need to know about the interactive CLI: what each role can do,
what every action means, how the screen output works, and how to test each scenario.

---

## Starting the CLI

```bash
cd /Users/devanshsaroja/Documents/a-Devolopment/ERISA/project
source .venv/bin/activate
python demo/crew_cli.py
```

Requires `ANTHROPIC_API_KEY` in your `.env` file. The compliance engine (87 tests) runs without an API key — only the natural-language interface needs it.

---

## Main Menu

When you start the CLI you see three roles:

```
1  Participant   — loans · deferrals · investments · distributions
2  Plan Sponsor  — approve queue · blackouts · audit log
3  Exit
```

Pick the role you want to act as. Each role has its own set of tools, scope, and allowed actions enforced by FAP Rule 1 (delegation validity).

---

## Role 1 — Participant

### What happens after you select Participant

You pick a participant from the list. Each line shows:

```
Amara Osei    PLAN-003  vested $85,000  loan headroom $42,500  5yr service · no loans
```

- **vested** — how much of the account balance is yours (employer match vesting matters for distributions)
- **loan headroom** — maximum you can borrow right now per IRC §72(p) math
- **7yr service** — years of vesting service (relevant to vesting schedule enforcement)
- **no loans / existing $25k loan** — whether outstanding loans exist (affects the IRC §72(p) cap)

Then you type in plain English. The system routes through:

```
Intent Agent → Data Agent (PLAP + PAAP) → Compliance Agent (FAP 12 rules) → Data Agent (execute) → Intent Agent (response)
```

---

### Participant Actions — Quick Reference

| Action | What it does | Autonomy | Demo Participant |
|---|---|---|---|
| `loan_initiation` | Borrow from your vested balance. Repaid via payroll deductions. Interest goes back to your own account. Max = lesser of $50k or 50% vested. | supervised | PART-008 Amara (no loans), PART-009 Daniela (cap demo) |
| `deferral_change` | Change what % of each paycheck goes to 401(k). Pre-tax or Roth. HCE >$145k catch-up must be Roth (SECURE 2.0). | full / supervised | Any active |
| `investment_reallocation` | Change which funds your money is in. Existing balance, future contributions, or both. Allocations must sum to 100%. | full | PART-008 Amara |
| `address_update` | Update mailing address. No ERISA compliance rules — administrative only. Fastest action to demo. | full | Any |
| `hardship_distribution` | Withdraw before 59½ for immediate financial need. Money is NOT repaid. Subject to income tax + 10% early withdrawal penalty. Sponsor must approve. | human_review | PART-008 Amara |
| `in_service_distribution` | Withdraw while still employed, only if age 59½+. Rare — most plans restrict until separation. | human_review | PART-006 Gabriel (age 61) |
| `separation_distribution` | Take your full balance after leaving the job (retired or terminated). 402(f) rollover notice must be issued first. | human_review | ⚠️ No retired participant in demo data |
| `rmd` | Process the IRS-required annual minimum withdrawal. Mandatory once you turn 73. RMD notice must be issued. | human_review | ⚠️ No rmd_required participant in demo data |
| `beneficiary_update` | Change who receives your account if you die. May require spousal consent depending on plan rules. | human_review | PART-008 Amara |
| `qdro` | Split account per court order in a divorce. Requires 5 legal fields. Plan sponsor makes qualification determination within 18 months. | human_review | PART-008 Amara (complex) |

---

### The 10 Participant Actions — Detail

Every action that changes something goes through all 12 FAP rules before anything executes.

---

#### 1. Loan Initiation — `loan_initiation`

**What it is:** Borrow from your own vested account balance. The money comes from your own investments, not from the employer. You repay via payroll deductions. The interest goes back into your own account.

**ERISA rule that governs it:** IRC §72(p) — max loan = lesser of:
- $50,000 minus the highest outstanding loan balance you've had in the last 12 months
- 50% of your vested balance

**Autonomy level:** `supervised` — you must type `confirm` before it executes.

**Term limits:**
- General purpose: max 5 years
- Primary residence purchase: max 15 years

**Example queries:**
```
I want to take out a $10,000 loan over 5 years
I want to borrow $25,000 to buy a house (15-year term)
How much can I borrow?
```

**What you see (success):**
```
RunComplianceCheck  loan_initiation  PART-008  →  APPROVED  autonomy=supervised
ExecuteTransaction  PART-008  loan_initiation  →  SUPERVISED_PENDING  awaiting confirmation

STATUS: Loan approved — pending your confirmation
Details:
- Amount: $10,000
- Term: 5 years
- ERISA rule: IRC §72(p) cap verified

Next Steps: Type 'confirm' to execute or 'cancel' to abort.

══════════════════════════════════════════════════
  CONFIRMATION REQUIRED
══════════════════════════════════════════════════
  Participant   PART-008
  Action        Loan Initiation
  Amount        $10,000.00
  Term          5 years
  Purpose       general purpose

  Type  confirm  to execute   ·   Type  cancel  to abort
══════════════════════════════════════════════════

confirm / cancel > confirm

  Transaction Executed
  EXECUTED
  Action      Loan Initiation
  Amount      $10,000.00
  Term        5 years
```

**What you see (denied):**
```
RunComplianceCheck  loan_initiation  PART-008  →  DENIED  LOAN_CAP_EXCEEDED

STATUS: Loan denied — IRC §72(p) cap exceeded
Details:
- You requested: $50,000
- Maximum allowed: $42,500 (50% of your $85,000 vested balance)
- ERISA rule: IRC §72(p) — loan cap

Next Steps: You may request up to $42,500.
```

---

#### 2. Deferral Change — `deferral_change`

**What it is:** Change the percentage of each paycheck that goes into your 401(k). You can change this at any time unless the plan is in a blackout.

**Pre-tax vs Roth:**
- Pre-tax: reduces your taxable income now, taxed when you withdraw
- Roth: no tax benefit now, tax-free in retirement

**Autonomy levels:**
- Increasing your deferral → `full` (executes immediately, no confirmation needed)
- Decreasing to 0% → `supervised` (stopping contributions is a big decision — confirm required)
- Any other decrease → `full`

**SECURE 2.0 rule (effective 2026):** If you earn more than $145,000 and are age 50+, catch-up contributions (the amount above $23,000) must be Roth. Pre-tax catch-up is blocked for high earners.

**Example queries:**
```
Change my deferral to 8% pre-tax
Set my contribution rate to 10% Roth
Set my deferral to 0%
Increase my deferral to 15% Roth
```

**Contribution limits (2024/2025):**
- Under 50: max $23,000/year
- Age 50+: max $30,500/year (adds $7,500 catch-up)
- Age 60–63 (SECURE 2.0): max $33,000/year (adds $10,000 catch-up)
- HCE earning >$145k: catch-up above $23k must be Roth

---

#### 3. Investment Reallocation — `investment_reallocation`

**What it is:** Change which funds your money is invested in. You can reallocate your existing balance, change where future contributions go, or both at once.

**Fund IDs — PLAN-003 (Capital One):**
| Fund ID | What it is | QDIA |
|---|---|---|
| COF-LIFEPATH-2025 through COF-LIFEPATH-2050 | BlackRock LifePath target-date funds | ✅ Yes |
| COF-SP500 | Fidelity 500 Index Fund | No |
| COF-BOND | Fidelity U.S. Bond Index Fund | No |
| COF-STABLE | Fidelity Managed Income Portfolio II | No |
| COF-INTL | Fidelity Total International Index Fund | No |
| COF-RUSSELL2500 | Vanguard Extended Market Index Fund | No |
| COF-CAPON | Capital One Company Stock Fund | No |

**Fund IDs — PLAN-004 (Prudential):**
| Fund ID | What it is | QDIA |
|---|---|---|
| PESP-GOALMAKER-AGG / -MOD / -CONS | GoalMaker model portfolios | ✅ Yes |
| PESP-SP500 | Vanguard Institutional 500 Index Trust | No |
| PESP-BOND | PGIM Core Plus Bond Fund | No |
| PESP-STABLE | Prudential Guaranteed Income Fund (GIF) | No |
| PESP-INTL | Vanguard Total International Stock Index Fund | No |
| PESP-SMIDCAP | Vanguard Extended Market Index Fund | No |
| PESP-PRU-STOCK | Prudential Company Stock Fund | No |

**QDIA:** Rebalancing to any QDIA fund (LifePath or GoalMaker) is always `full` autonomy — executes immediately, no confirmation needed.

**Autonomy level:** `full` — executes immediately.

**Example queries (Capital One):**
```
Reallocate my investments: 60% COF-SP500 and 40% COF-LIFEPATH-2040
Move everything to the target-date 2040 fund
Change future contributions to 100% COF-BOND
Reallocate to 70% COF-SP500, 20% COF-INTL, 10% COF-STABLE
```

**Example queries (Prudential):**
```
Reallocate to 80% PESP-GOALMAKER-MOD and 20% PESP-STABLE
Move everything to PESP-SP500
```

**Allocation rules:** Allocations must add up to exactly 100%. FAP will reject if they don't.

---

#### 4. Hardship Distribution — `hardship_distribution`

**What it is:** Withdraw money from your account before age 59½ due to an immediate and heavy financial need. Unlike a loan, this money does not get repaid. It is taxed as ordinary income and subject to a 10% early withdrawal penalty.

**IRS safe harbor expense types (the only ones the plan is required to allow):**

| Expense type | Example |
|---|---|
| `medical` | Unreimbursed medical expenses for you, spouse, or dependent |
| `housing_purchase` | Down payment on a primary home |
| `tuition` | Tuition and education fees (next 12 months) |
| `eviction_foreclosure` | Prevent eviction from or foreclosure on your primary home |
| `funeral` | Burial or funeral expenses for a family member |
| `casualty_loss` | Damage to your primary home from disaster |
| `emergency_personal_expense` | SECURE 2.0: up to $1,000 for any personal emergency |

If your plan has the `six_month_contribution_suspension` legacy provision (pre-2019), you cannot make new contributions for 6 months after a hardship withdrawal.

**Autonomy level:** `human_review` — the plan sponsor must approve before anything is paid out. Not automated — a human reviews every hardship request.

**Document requirement:** After the queue entry is created, the CLI immediately prompts for document upload. The plan sponsor **cannot approve until verified documents are on file** — the Approve command is blocked.

```
Document types accepted by expense:
  medical          → medical bill, hospital statement, doctor invoice, EOB
  tuition          → tuition invoice, enrollment verification, financial aid letter
  prevent_eviction → eviction notice, foreclosure letter, utility shutoff notice
  funeral          → funeral invoice, death certificate
  primary_home_purchase → purchase agreement, contractor estimate, builder contract
  casualty_loss    → insurance claim, damage assessment
  FEMA_disaster    → FEMA declaration, damage proof
```

**Example queries:**
```
I need a $5,000 hardship withdrawal for a medical emergency
I need money for my daughter's tuition — $8,000
I need $3,000 to avoid foreclosure on my home
```

---

#### 5. In-Service Distribution — `in_service_distribution`

**What it is:** Withdraw from your account while still actively employed. Only allowed at age 59½ or older for most plans. No need to terminate employment first.

**Autonomy level:** `human_review` — sponsor must approve.

**When this gets blocked:** If you are under 59½, FAP Rule 7 will deny it with `IN_SERVICE_AGE_NOT_MET`. The 10% early withdrawal penalty would also apply (Rule 7).

**Example queries:**
```
I'd like to make a withdrawal from my account — I'm 62
I want to take an in-service distribution
```

**Demo participant:** PART-006 Gabriel Stone (age 61, active, Capital One) — he is active and over 59½, so in-service distribution is permitted. To demo the denial: use PART-008 Amara (age 36, active) — FAP Rule 6 fires: `IN_SERVICE_AGE_NOT_MET`.

---

#### 6. Separation Distribution — `separation_distribution`

**What it is:** Withdraw your full balance after leaving the job (terminated, retired, or laid off). PAAP requires that a 402(f) rollover notice has been issued before it will process this — the notice explains your options (roll over to IRA vs. take the cash).

**Autonomy level:** `human_review` — sponsor must approve.

**What gets blocked:** Active employees (employment_status = active) cannot request this — FAP Rule 6 blocks it. A 402(f) notice must be on file.

**Good demo participant:** No retired participant in current demo data. To demo the denial: use PART-008 Amara (active, age 36) — FAP Rule 6 fires: `SEPARATION_STATUS_INVALID`. To demo the approval flow, a retired or terminated participant would need to be added.

---

#### 7. Required Minimum Distribution — `rmd`

**What it is:** Once you turn 73, the IRS requires you to withdraw a minimum amount from your 401(k) every year. Aldergate enforces the rule that an RMD notice must be issued before processing the distribution.

**Autonomy level:** `human_review` — coordinated with the plan sponsor.

**What gets blocked:** If `rmd_required=False` on the participant record, FAP blocks it immediately (RMD_NOT_YET_REQUIRED). If the notice hasn't been issued, FAP blocks it (RMD_NOTICE_NOT_ISSUED). If the amount is below the required minimum, FAP blocks it (RMD_AMOUNT_INSUFFICIENT).

**Good demo participant:** No participant with `rmd_required=True` in current demo data (RMD applies at age 73; youngest eligible is Gabriel at 61). To demo the denial: use PART-008 Amara — FAP Rule 11 fires immediately: `RMD_NOT_YET_REQUIRED`.

---

#### 8. Beneficiary Update — `beneficiary_update`

**What it is:** Change who receives your account balance if you die. In plans subject to QJSA rules, spousal consent may be required. Every beneficiary change is routed for human review.

**Autonomy level:** `human_review` — plan sponsor records the change.

**Spousal consent (ERISA § 205 / QJSA):** Capital One's plan requires spousal consent for beneficiary changes. FAP handles this without ever seeing marital status directly (PII rule). Three outcomes:
- Spousal consent not mentioned → APPROVED with condition "spousal consent status unconfirmed — human review required"
- `spousal_consent_obtained=True` passed → APPROVED, sponsor confirms
- `spousal_consent_obtained=False` passed → DENIED `QJSA_CONSENT_REQUIRED`

**Example queries:**
```
I want to update my beneficiary to my daughter Jane Doe
Change my beneficiary to my son — my spouse has given written consent
Change my beneficiary to my domestic partner
```

**What you see (approved with condition):**
```
RunComplianceCheck  beneficiary_update  PART-008  →  APPROVED  autonomy=human_review
  condition: Spousal consent status not confirmed — human review required.
ExecuteTransaction  PART-008  →  QUEUED_FOR_HUMAN_REVIEW
```

**What you see (denied — no consent):**
```
RunComplianceCheck  beneficiary_update  PART-008  →  DENIED  QJSA_CONSENT_REQUIRED
  Rule 6: This plan requires written spousal consent (witnessed by a plan
  representative or notary public) for beneficiary changes under ERISA § 205.
```

---

#### 9. QDRO — `qdro`

**What it is:** Qualified Domestic Relations Order — a court order that splits your retirement account as part of a divorce settlement. The alternate payee (your ex-spouse) receives a defined portion. ERISA requires the plan sponsor to make a "qualified status" determination within 18 months.

**Autonomy level:** `human_review` — legal order, must be reviewed by the plan sponsor.

**Document requirement:** After queuing, the CLI prompts to upload the signed court order. Sponsor Approve is blocked until the QDRO court order document is verified.

**5 required fields (FAP Rule 6 checks all of them):**
| Field | What it is |
|---|---|
| `participant_name` | Full legal name of the account holder |
| `alternate_payee_name` | Full legal name of the ex-spouse receiving the split |
| `plan_name` | Full plan name as it appears in the SPD |
| `benefit_amount_or_pct` | Dollar amount or percentage being transferred (e.g. "50%") |
| `payment_period` | When the transfer happens (e.g. "during accumulation phase") |

If any field is missing → DENIED `QDRO_FIELDS_MISSING` listing the exact missing fields.

**Example query (include all 5 fields in plain English):**
```
I need to process a QDRO. Participant: Amara Osei. Alternate payee: Thomas Osei.
Plan: Capital One Associate Savings Plan. Amount: 50% of vested balance.
Payment period: during accumulation phase.
```

**What you see (approved):**
```
RunComplianceCheck  qdro  PART-008  →  APPROVED  autonomy=human_review
ExecuteTransaction  PART-008  →  QUEUED_FOR_HUMAN_REVIEW
```

**What you see (denied — missing fields):**
```
RunComplianceCheck  qdro  PART-008  →  DENIED  QDRO_FIELDS_MISSING
  Rule 6: QDRO is missing required fields: alternate_payee_name, benefit_amount_or_pct, payment_period.
```

---

#### 10. Address Update — `address_update`

**What it is:** Change your mailing address on file. No ERISA compliance rules apply — this is a pure administrative update. Executes immediately with no confirmation required.

**Autonomy level:** `full` — executes immediately.

**Example queries:**
```
Update my address to 456 Oak Street, Chicago, IL 60601
Change my address to 789 Maple Ave, Austin, TX 78701
```

---

### Participant Action Summary Table

| Action | Autonomy | Demo Participant | Status |
|---|---|---|---|
| loan_initiation | supervised | PART-008 Amara (no loans), PART-009 Daniela (cap exceeded) | ✅ Works |
| deferral_change | full / supervised | Any active participant | ✅ Works |
| investment_reallocation | full | PART-008 Amara (use valid fund IDs) | ✅ Works |
| address_update | full | Any participant | ✅ Works |
| hardship_distribution | human_review | PART-008 Amara | ✅ Works |
| beneficiary_update | human_review | PART-008 Amara | ✅ Works |
| separation_distribution | human_review | No retired participant | ⚠️ Can demo denial only (active employees blocked) |
| rmd | human_review | No rmd_required participant | ⚠️ Can demo denial only (RMD_NOT_YET_REQUIRED) |
| in_service_distribution | human_review | PART-006 Gabriel (age 61) | ✅ Works |
| qdro | human_review | PART-008 Amara (include all 5 fields in query) | ✅ Works — give LLM all 5 fields explicitly |

---

## Role 2 — Plan Sponsor

### What happens after you select Plan Sponsor

You select a plan (PLAN-003 or PLAN-004). The system gives you a command interface for administration tasks. No compliance check is needed for read-only operations — only writes go through FAP.

### Plan Sponsor Actions

| Action | What it does |
|---|---|
| View pending queue | See all transactions waiting for human approval. Shows document status for hardship/QDRO entries. |
| View documents | Read uploaded documents, LLM verification result, and approval status for a queue entry |
| Approve documents | Explicitly mark documents as reviewed and accepted (required before approving hardship/QDRO request) |
| Approve a request | Mark the queued request as approved. **Blocked for hardship/QDRO until `approve doc` has been run.** |
| Deny a request | Reject a queued item with a reason; writes a denial record to the audit log |
| Activate blackout | Freeze all participant write operations. ERISA §101(i) requires 30-day advance notice to participants |
| Deactivate blackout | Lift the freeze |
| View audit log | Read every FAP decision (approved AND denied) — 6-year ERISA §107 retention requirement |
| Check blackout status | See whether the plan is currently in a blackout period |

### Example sponsor queries

**Fast-path (instant, no LLM):**
```
queue                                          ← all pending review items (shows doc status)
docs <entry_id>                               ← read uploaded documents + LLM verification note
approve doc <entry_id>                        ← approve the documents (required step for hardship/QDRO)
Approve <entry_id> — <note>                   ← approve the request (blocked until docs approved)
Deny <entry_id> — <reason>                    ← deny the request
audit                                          ← last 10 FAP audit entries
blackout status                                ← whether a blackout is active
```

**Hardship / QDRO approval — 3 steps:**
```
Step 1:  docs AB064BBC              ← read the document and LLM verification
Step 2:  approve doc AB064BBC       ← explicitly approve the document
Step 3:  Approve AB064BBC — note    ← approve the request (only works after Step 2)
```

Other human_review actions (beneficiary, separation, RMD) skip Steps 1–2 and go straight to `Approve`.

**Via CrewAI (20–40 seconds) — only for these:**
```
Activate a blackout from 2026-08-15 to 2026-09-01 for recordkeeper transition
Deactivate the blackout
What does our plan allow for hardship distributions?
```

### The Review Queue

Every `human_review` transaction from participants lands here. The sponsor sees:
- Entry ID (reference number)
- Participant ID
- Action type
- Amount and payload
- FAP audit ID and token

The sponsor either approves (ExecuteTransaction runs) or denies (audit record written, token discarded).

---

## Role 3 — Investment Advisor

### What happens after you select Investment Advisor

You select a client (participant). The advisor is only registered for PLAN-003 (Capital One) — selecting a PLAN-004 client is blocked at Rule 1 (delegation scope exceeded).

**Scope is limited:** Advisors can only submit `investment_reallocation` and `deferral_change` recommendations. They cannot initiate loans, hardship withdrawals, or distributions.

### Advisor Actions

| Action | What it does | Autonomy |
|---|---|---|
| View fund lineup | See all funds in the plan, including QDIA designation | n/a (read-only) |
| View client elections | See the client's current fund allocations | n/a (read-only) |
| Submit reallocation | Recommend new fund allocations for the client | supervised or human_review |
| Submit deferral change | Recommend a new contribution rate for the client | full or supervised |

### Example advisor queries

```
Show me the fund lineup for this plan
What are my client's current investment elections?
Reallocate my client to 70% COF-SP500 and 30% COF-LIFEPATH-2040
Change my client's deferral to 10% pre-tax
Recommend a rebalance to the target-date fund
```

### Why advisors are restricted

FAP Rule 9 (Prohibited Transaction — ERISA §406) enforces PTE 2020-02. An advisor recommending a rollover or reallocation creates a potential conflict of interest. If the advisor doesn't have the right PTE exemption, the transaction is blocked.

---

## Navigating the CLI

**Role switching:** type `back` (or `exit`, `quit`) at any prompt to return to the main role menu. No restart needed.

**Sponsor fast-path** — these commands skip the LLM entirely (instant, no API cost):
```
queue           ← all pending review items
audit           ← last 10 FAP audit entries
blackout status ← whether a blackout is active
```

Everything else goes through the full CrewAI crew (20–45 seconds, 6 LLM calls).

---

## Understanding the Screen Output

Steps appear live as they happen — you do not wait for everything to finish before seeing output.

### Live Step Display

```
  [1]  Intent Agent — parsing query...

  [2]  Data Agent — plan rules
       ✓  GetPlanRules               PLAN-003            → plan data

  [3]  Data Agent — participant data
       ✓  GetParticipantSummary      PART-008            → participant data
       ✓  GetLoanHeadroom            PART-008            → headroom: $42,500

  [4]  Compliance Agent — FAP · 12 ERISA rules
       ✓  RunComplianceCheck         loan_initiation     → APPROVED  autonomy=supervised

       ✓  Rule  1  Delegation Validity             ERISA §404
       ✓  Rule  2  Blackout Period                 ERISA §101(i)
       ✓  Rule  3  Participation & Eligibility     ERISA §202
       ✓  Rule  4  Vesting Enforcement             ERISA §203
       ✓  Rule  5  Contribution Limits             IRC §402(g)
       ✓  Rule  6  Plan Rules                      plan-specific
       ✓  Rule  7  Early Withdrawal Penalty        IRC §72(t)
       ✓  Rule  8  Anti-Alienation                 ERISA §206(d)
       ✓  Rule  9  Prohibited Transaction          ERISA §406
       ✓  Rule 10  Prudent Expert                  ERISA §404
       ✓  Rule 11  RMD Failure Prevention          IRC §401(a)(9)
       ✓  Rule 12  Autonomy Level Assignment       SUPERVISED  → JWT token issued

  [5]  Data Agent — execute / queue transaction
       ✓  ExecuteTransaction         PART-008            → SUPERVISED_PENDING

  [6]  Intent Agent — composing response...
```

A denial stops at the failing rule — remaining rules are not evaluated (fail-fast):
```
       ✗  Rule  6  Plan Rules                      FAIL  ← LOAN_CAP_EXCEEDED
            Rules 7–12 not evaluated (fail-fast)
```

**What each RunComplianceCheck result means:**
- `APPROVED  autonomy=supervised` — all 12 rules passed; participant must confirm
- `APPROVED  autonomy=full` — all 12 rules passed; executes immediately
- `APPROVED  autonomy=human_review` — passed; queued for sponsor approval
- `DENIED  LOAN_CAP_EXCEEDED` — Rule 6 fired; denied with that code
- `DENIED  BLACKOUT_ACTIVE` — Rule 2 fired; rules 3–12 skipped
- `SUPERVISED_PENDING` — transaction held, waiting for `confirm`
- `EXECUTED` — transaction went through
- `QUEUED_FOR_HUMAN_REVIEW` — in the sponsor queue

### Response Format

```
STATUS: [one-line summary]

Details:
- [key fact]
- [key fact]

Next Steps: [what to do]
```

### Confirmation Panel (supervised only)

Appears automatically after a supervised approval:

```
══════════════════════════════════════════════════════
  CONFIRMATION REQUIRED
══════════════════════════════════════════════════════
  FAP approved this transaction, but it carries financial impact.
  All 12 ERISA rules passed. Your explicit confirmation is required.

  Participant   PART-008
  Action        Loan Initiation
  Amount        $10,000.00
  Term          5 years

  Type  confirm  to execute   ·   Type  cancel  to abort
══════════════════════════════════════════════════════
```

The input prompt changes to `confirm / cancel >` while you're in this state.
- `confirm` → executes immediately, shows Transaction Executed
- `cancel` → clears the pending transaction, nothing executes
- Anything else → clears pending and treats it as a new query

---

## Participants Reference

| ID | Name | Age | Vested | Plan | Key Notes |
|---|---|---|---|---|---|
| PART-006 | Gabriel Stone | 61 | $210,000 | PLAN-003 | HCE ($185k comp), catch-up eligible, near retirement — demo SECURE 2.0 + in-service distribution |
| PART-007 | Yuki Tanaka | 31 | $38,000 | PLAN-004 | 1.5yr service, cliff vesting not met on either plan — demo vesting enforcement |
| PART-008 | Amara Osei | 36 | $85,000 | PLAN-003 | 5yr service, no loans — **primary demo participant** |
| PART-009 | Daniela Reyes | 41 | $100,000 | PLAN-003 | Existing $25k loan — reduces IRC §72(p) headroom to $25k |

## Plans Reference

| ID | Name | Key Properties |
|---|---|---|
| PLAN-003 | Capital One Associate Savings Plan | Safe harbor, immediate eligibility (age 18), 2yr cliff vesting, loans permitted (5yr/10yr), up to 2 concurrent loans |
| PLAN-004 | Prudential Employee Savings Plan (PESP) | 1yr service wait, 3yr cliff vesting, loans permitted (5yr/15yr), max 1 loan |

## Agent Registry

| Agent ID | Role | Scope |
|---|---|---|
| AGENT-PARTICIPANT-001 | participant | All actions, PLAN-003 + PLAN-004 |
| AGENT-ADVISOR-001 | investment_advisor | investment_reallocation + deferral_change, PLAN-003 only |
| AGENT-SPONSOR-001 | plan_sponsor | beneficiary_update + qdro + rmd, all plans |
| AGENT-INACTIVE-001 | (inactive) | Always blocked at Rule 1 |

---

## Connection Errors

If the CLI shows:

```
Connection error — could not reach the Anthropic API.
Check your internet connection and try again.
```

This means the API call failed due to network connectivity. The compliance engine (FAP) and all mock data are still intact — only the LLM couldn't be reached. Wait a moment and retry the same query.

Other possible errors:
- `Authentication error` — check ANTHROPIC_API_KEY in your `.env` file
- `Rate limit reached` — too many requests; wait a few seconds and retry

---

## Running Without an API Key (Compliance Engine Only)

The entire FAP compliance engine runs in pure Python with no API key. Use this to test rules in isolation:

```bash
# Direct compliance check — no LLM
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

# Run all 87 tests
pytest tests/ -v
```
