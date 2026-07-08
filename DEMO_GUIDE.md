# Aldergate — Complete Demo Guide (All Participants × All Actions)

## Setup

```bash
cd /Users/devanshsaroja/Documents/a-Devolopment/ERISA/project
source .venv/bin/activate
python demo/crew_cli.py
```

`ANTHROPIC_API_KEY` must be set in `.env`. `DATABASE_URL` must point to the running PostgreSQL instance.

---

## Navigation

```
Main menu → pick role → session prompt
  Participant >    ← natural language queries
  Sponsor >        ← queue management
  back / exit      ← return to role menu without restarting
```

**Participant instant reads (no LLM, instant):**
```
balance          → vested balance, loans, fund elections
my investments   → fund allocation bar chart
my deferral      → rate, type, YTD breakdown
my employment    → status, hire date, vesting, service years
my plan          → plan name, loan/hardship/in-service rules
ytd              → employee + employer contributions year-to-date
how much can I borrow → IRC §72(p) max loan
status           → pending/approved queue items
my beneficiary   → note (Phase 5 pending)
my address       → note (Phase 5 pending)
```

**Sponsor instant commands (no LLM, instant):**
```
queue                     → pending review items
audit                     → last 10 FAP decisions
blackout status           → current blackout state
Approve <ID> — <note>    → approve a queue item
Deny <ID> — <reason>     → deny a queue item
```

---

## How Live Output Looks

Every write request streams agent steps as they happen:

```
  [1]  Intent Agent — parsing query...
  [2]  Data Agent — plan rules          ✓  GetPlanRules
  [3]  Data Agent — participant data    ✓  GetParticipantSummary   ✓  GetLoanHeadroom
  [4]  Compliance Agent — FAP · 12 rules
       ✓  RunComplianceCheck            APPROVED  autonomy=supervised
       ✓  Rule  1  Delegation Validity             ERISA §404
       ...
       ✓  Rule 12  Autonomy Assignment             SUPERVISED → JWT issued
  [5]  Data Agent — execute             ✓  ExecuteTransaction
  [6]  Intent Agent — composing response...
```

A denial stops at the first failing rule. Rules below it are not evaluated (fail-fast).

---

## Participants at a Glance

| ID | Name | Plan | Age | Vested | Loans | HCE | Key trait |
|---|---|---|---|---|---|---|---|
| PART-008 | Amara Osei | PLAN-003 Capital One | 36 | $85k | 0 | No | Primary demo — clean slate |
| PART-006 | Gabriel Stone | PLAN-003 Capital One | 61 | $210k | 0 | Yes ($185k) | Near-retirement · SECURE 2.0 catch-up · in-service eligible |
| PART-009 | Daniela Reyes | PLAN-003 Capital One | 41 | $100k | 1 ($22k bal) | No | Existing loan → §72(p) cap demo |
| PART-007 | Yuki Tanaka | PLAN-004 Prudential | 31 | $38k | 0 | No | 1.5yr service · 0% employer vesting (cliff at 3yr) |

**Plan comparison:**

| | PLAN-003 Capital One | PLAN-004 Prudential |
|---|---|---|
| Safe harbor | Yes | No |
| Loans | Yes · max 2 outstanding | Yes · max 1 outstanding |
| Hardship | Yes · safe harbor standard | Yes · safe harbor standard |
| In-service (59½+) | Yes | Yes |
| Vesting | Immediate (match) | 3-yr cliff |
| Eligibility | Immediate | 1 year |

---

---

## PART-008 — Amara Osei · Capital One · Primary Demo

**Profile:** Age 36 · $85k vested · 100% vesting · 5yr service · no loans · not HCE · not RMD
**Max loan:** $42,500 (50% × $85k)
**Current deferral:** 6% pre-tax · emp YTD $8,000 · er YTD $5,060
**Funds:** 70% COF-LIFEPATH-2040 · 30% COF-SP500

### Action Summary

| # | Action | Status | Result |
|---|---|---|---|
| 1 | Loan — approved | ✅ WORKS | supervised confirm/cancel |
| 2 | Loan — over cap | ✅ DENIES | LOAN_CAP_EXCEEDED |
| 3 | Deferral increase | ✅ WORKS | full autonomy (executes immediately) |
| 4 | Deferral to 0% | ✅ WORKS | supervised confirm/cancel |
| 5 | Hardship — medical | ✅ WORKS | human_review → sponsor queue |
| 6 | Investment reallocation | ✅ WORKS | full autonomy (executes immediately) |
| 7 | Beneficiary — no consent | ✅ WORKS | approved with condition → human_review |
| 8 | Beneficiary — consent denied | ✅ DENIES | QJSA_CONSENT_REQUIRED |
| 9 | Address update | ✅ WORKS | full autonomy (executes immediately) |
| 10 | In-service distribution | ✅ DENIES | IN_SERVICE_AGE_NOT_MET (age 36) |
| 11 | Separation distribution | ✅ DENIES | SEPARATION_STATUS_INVALID (active) |
| 12 | QDRO — all fields | ✅ WORKS | human_review → sponsor queue |
| 13 | QDRO — missing fields | ✅ DENIES | QDRO_FIELDS_MISSING |
| 14 | RMD | ✅ DENIES | RMD_NOT_YET_REQUIRED (age 36) |

---

### 1. Loan — Approved (Supervised)

```
I want to take out a $10,000 loan over 5 years
```

- Rule 6: $10k ≤ $42,500 headroom ✓ · term 5yr ≤ 5yr general max ✓
- Rule 12: **supervised** — loan initiation always requires participant confirmation

After crew runs → CLI shows confirmation panel automatically:
```
  CONFIRMATION REQUIRED
  Action      Loan Initiation
  Amount      $10,000.00
  Term        5 years
```
Type `confirm` to execute · `cancel` to abort.

**Note:** The FAP token is issued but not consumed until `confirm`. Typing `cancel` invalidates the token with no API cost.

---

### 2. Loan — Over Cap (Denied)

```
I want to borrow $50,000
```

- Rule 6 fires: max loan = min($50k − $0 prior, 50% × $85k) = **$42,500**
- $50k > $42,500 → **LOAN_CAP_EXCEEDED**
- Rules 7–12 not evaluated

---

### 3. Deferral Increase (Full Autonomy)

```
Change my deferral to 8% pre-tax
```

- Rule 5: 8% × $92k comp = $8,280 projected annual — well under $23k limit ✓
- Rule 12: **full** — increasing savings executes immediately, no confirm needed

After execution, type `my deferral` to see updated rate instantly.

---

### 4. Deferral to 0% (Supervised)

```
Set my deferral to 0%
```

- All 12 rules pass
- Rule 12: **supervised** — stopping contributions is a major financial decision

Confirm panel will appear. Type `confirm` to execute.

**What to point out:** Same action type (`deferral_change`), different direction → different autonomy level. Rule 12 uses business logic, not just the action name.

---

### 5. Hardship Distribution — Medical (Human Review + Document Upload)

```
I need a $5,000 hardship withdrawal for a medical emergency
```

- Rule 6: medical = valid safe harbor expense ✓ · PLAN-003 permits hardship ✓
- Rule 12: **human_review** — hardship is taxable, irreversible, requires fiduciary oversight

After the crew runs → queue entry created (e.g., `AB12CD34`). CLI immediately prompts:

```
  DOCUMENT UPLOAD REQUIRED
  ─────────────────────────────────────────────────
  Hardship: medical
  Please upload: medical bill, hospital statement, or doctor invoice

  [1]  Use sample document  (Metro General Hospital medical bill)
  [2]  Enter file path
  [3]  Skip (request stays pending, sponsor cannot approve until docs uploaded)
  ─────────────────────────────────────────────────
```

Select `1` → Claude Haiku verifies automatically:
```
  ✓ Verified  medical_bill.txt
  "Medical bill from Metro General Hospital, 2026-05-14, patient balance $1,865.00"
```

**To continue the demo as plan sponsor:**
1. Type `back` → pick Plan Sponsor → pick PLAN-003
2. Type `queue` → see the entry with `📎 1 doc  (LLM verified · awaiting your review)`
3. Type `docs AB12CD34` → read the document content, LLM verification note, and "Awaiting your approval" status
4. Type `approve doc AB12CD34` → "Document approved. You may now approve the request."
5. Type `Approve AB12CD34 — valid medical documentation provided`

**What to point out:** Three separate steps — read, approve doc, approve request. The LLM auto-verification is the first check; sponsor document approval is the second. Only after both can the request be approved. This mirrors real ERISA fiduciary practice where the plan sponsor must personally verify hardship documentation.

---

### 6. Investment Reallocation (Full Autonomy)

```
Reallocate my investments: 60% COF-SP500 and 40% COF-LIFEPATH-2040
```

- Rule 12: **full** — investment changes have no withdrawal consequence
- Executes immediately, no confirm panel

After execution, type `my investments` to see the updated allocation instantly.

**Variations:**
```
Move everything to COF-LIFEPATH-2040
```
```
Split 50% COF-SP500, 30% COF-BOND, 20% COF-STABLE
```

**What to point out:** Allocations must sum to exactly 100%. If they don't, FAP rejects the payload before any rule runs.

---

### 7. Beneficiary Update — No Consent Provided (Approved with Condition)

```
I want to update my beneficiary to my daughter Jane Osei
```

- Rule 6: plan requires QJSA spousal consent check; no consent info in payload → **approved with condition**
- Rule 12: **human_review** — sponsor verifies consent during review

FAP never asks about marital status. It receives a boolean for `spousal_consent_obtained`. When absent → approved with condition (not denied). Sponsor resolves during review.

---

### 8. Beneficiary Update — Consent Explicitly Denied

```
I want to change my beneficiary to my domestic partner — my spouse has not given consent
```

- Rule 6 fires: `spousal_consent_obtained=False` → **QJSA_CONSENT_REQUIRED** denied
- "This plan requires written spousal consent (witnessed by a plan representative or notary public) for beneficiary changes under ERISA §205."
- No token issued. Nothing queued.

**What to point out:** The LLM extracted `spousal_consent_obtained=False` from the plain English. FAP enforced ERISA §205 — without ever knowing who the spouse is.

---

### 9. Address Update (Full Autonomy)

```
Update my address to 789 Maple Ave, Austin, TX 78701
```

- Rule 12: **full** — administrative actions carry no ERISA financial risk
- Executes immediately. No confirm panel, no sponsor queue.

---

### 10. In-Service Distribution (Denied — Age 36)

```
I'd like to make an in-service withdrawal from my account
```

- Rule 6 fires: age 36 < 59½ → **IN_SERVICE_AGE_NOT_MET**
- Rules 7–12 not evaluated

**Contrast with Gabriel Stone (PART-006, age 61):** same query passes Rule 6. Shows how the same action produces different results depending on participant age — with the LLM never seeing the date of birth.

---

### 11. Separation Distribution (Denied — Active Employee)

```
I want to take my full balance as a separation distribution — the rollover notice was sent
```

- Rule 6 fires: status = `active` → **SEPARATION_STATUS_INVALID**
- "Separation distributions require employment_status of 'terminated' or 'retired'. Current status: 'active'."
- The 402(f) notice being "issued" is irrelevant — Rule 6 checks employment status first (fail-fast).

---

### 12. QDRO — All 5 Fields (Approved, Human Review + Document Upload)

```
I need to process a QDRO. Participant: Amara Osei. Alternate payee: Thomas Osei.
Plan: Capital One Associate Savings Plan. Amount: 50% of vested balance.
Payment period: during accumulation phase.
```

- All 12 rules pass
- Rule 12: **human_review** — plan sponsor determines qualification within 18 months (ERISA §206(d))
- Queued with all 5 legal order fields on record

After queuing, CLI immediately prompts to upload the signed court order:
```
  [1]  Use sample document  (Cook County Circuit Court QDRO)
  [2]  Enter file path
  [3]  Skip
```

Select `1` → Claude Haiku verifies: ✓ "Qualified Domestic Relations Order, Cook County, 50% of vested balance, May 8 2026"

Sponsor then: `docs <entry_id>` to read the order · `Approve <entry_id> — QDRO verified` to approve.

---

### 13. QDRO — Missing Fields (Denied)

```
I need to process a QDRO for my divorce — split 50% with my ex
```

- Rule 6 fires: **QDRO_FIELDS_MISSING**
- "Missing: participant_name, alternate_payee_name, plan_name, payment_period."
- FAP reads required fields from the plan's SPD configuration, not hardcoded.

---

### 14. RMD (Denied — Not Required)

```
I need to process my required minimum distribution of $10,000
```

- Rule 6 fires: `rmd_required=False` (age 36) → **RMD_NOT_YET_REQUIRED**

---
---

## PART-006 — Gabriel Stone · Capital One · Near-Retirement / HCE

**Profile:** Age 61 · $210k vested · 100% vesting · 27yr service · no loans · HCE ($185k comp) · not RMD
**Max loan:** $50,000 (no prior loans; 50% × $210k = $105k > $50k cap)
**Current deferral:** 10% pre-tax · emp YTD $23,000 (at base limit) · er YTD $10,350
**Funds:** 60% COF-LIFEPATH-2030 · 25% COF-SP500 · 15% COF-STABLE
**Catch-up:** Age 60–63 SECURE 2.0 enhanced catch-up ($10,000 extra/yr above the $23k base)

### Action Summary

| # | Action | Status | Result |
|---|---|---|---|
| 1 | Loan — approved | ✅ WORKS | supervised · max $50k |
| 2 | Deferral to 15% pre-tax | ✅ DENIES | ROTH_CATCHUP_REQUIRED (SECURE 2.0) |
| 3 | Deferral to 15% Roth | ✅ WORKS | supervised |
| 4 | Deferral reduce to 5% | ✅ WORKS | full autonomy |
| 5 | Hardship | ✅ WORKS | human_review |
| 6 | Investment reallocation | ✅ WORKS | full autonomy |
| 7 | Beneficiary update | ✅ WORKS | human_review |
| 8 | Address update | ✅ WORKS | full autonomy |
| 9 | In-service distribution | ✅ WORKS | human_review · age 61 ≥ 59½ |
| 10 | Separation distribution | ✅ DENIES | SEPARATION_STATUS_INVALID (active) |
| 11 | QDRO | ✅ WORKS | human_review |
| 12 | RMD | ✅ DENIES | RMD_NOT_YET_REQUIRED (age 61, rule starts at 73) |

---

### 1. Loan — Large Amount (Supervised)

```
I want to take out a $40,000 loan over 5 years
```

- Rule 6: $40k ≤ $50k headroom ✓ (50% × $210k = $105k, but IRC cap is $50k max)
- Rule 12: **supervised**

```
I want to borrow $50,000 over 5 years
```

Max allowed: $50,000 exactly (lesser of $50k IRS cap and 50% × $210k = $105k).

---

### 2. Deferral to 15% Pre-Tax (SECURE 2.0 Denial — Key Demo)

```
Increase my deferral to 15% pre-tax
```

- 15% × $185k = $27,750/yr projected
- $27,750 > $23,000 base limit → catch-up territory triggered
- Gabriel: HCE · income $185k > $145k threshold · age 60–63
- Rule 5 fires: **ROTH_CATCHUP_REQUIRED**
- "SECURE 2.0 §603 (effective 2026): HCEs earning more than $145,000 must designate all catch-up contributions as Roth."

**What to point out:** This rule became mandatory January 1, 2026. Gabriel cannot accidentally violate it — the system blocks pre-tax catch-up for HCEs automatically. The LLM never made this decision; FAP's pure Python did.

---

### 3. Deferral to 15% Roth (Approved — SECURE 2.0 Satisfied)

```
Change my deferral to 15% Roth
```

- Same math, but `deferral_type=roth` → SECURE 2.0 requirement satisfied ✓
- Rule 12: **supervised** (deferral change affects ongoing contributions)

Then `confirm` to execute. After that, `my deferral` shows the new rate instantly.

---

### 4. Deferral Reduce to 5% Pre-Tax (Full Autonomy)

```
Reduce my deferral to 5% pre-tax
```

- 5% × $185k = $9,250 — under the base limit, no catch-up needed ✓
- Rule 12: **full** — reducing (but not to 0%) executes immediately

---

### 5. Hardship Distribution (Human Review)

```
I need $8,000 for medical bills from last month's emergency
```

All rules pass · Rule 12: **human_review** — same as PART-008 but larger amount.

---

### 6. Investment Reallocation (Full Autonomy)

Current: 60% COF-LIFEPATH-2030 · 25% COF-SP500 · 15% COF-STABLE

```
Move me to 80% COF-LIFEPATH-2025 and 20% COF-STABLE
```

He's 61 — shifting toward a shorter-dated target fund is realistic. Full autonomy, executes immediately.

```
Move everything to the QDIA — COF-LIFEPATH-2025
```

---

### 7. Beneficiary Update (Human Review)

```
I want to designate my spouse Maria Stone as primary beneficiary
```

Rule 6: consent not explicitly provided → approved with condition · **human_review**

---

### 8. Address Update (Full Autonomy)

```
Update my address to 450 Park Avenue, New York, NY 10022
```

Full autonomy · executes immediately.

---

### 9. In-Service Distribution (Approved — Best Gabriel Demo)

```
I'd like to make an in-service withdrawal from my account
```

- Rule 6: age 61 ≥ 59½ · in-service distribution permitted in PLAN-003 ✓
- Rule 12: **human_review** — plan sponsor must approve; significant financial decision

**This is the strongest contrast demo:** switch immediately to PART-008 (age 36) and run the same query → **IN_SERVICE_AGE_NOT_MET**. Same words, different person, completely different compliance result. FAP never saw the date of birth — it only received a boolean `age_59_5_or_older`.

---

### 10. Separation Distribution (Denied — Still Active)

```
I want to take a separation distribution — rollover notice was issued
```

Rule 6 fires: status = `active` → **SEPARATION_STATUS_INVALID**

(Gabriel hasn't retired yet. If he retires and comes back as PART-006 with status `retired`, this path opens.)

---

### 11. QDRO (Human Review)

```
Process a QDRO. Participant: Gabriel Stone. Alternate payee: Linda Stone.
Plan: Capital One Associate Savings Plan. Amount: 40% of vested balance.
Payment period: until alternate payee reaches age 65.
```

Rule 12: **human_review** · ERISA §206(d) — 18-month determination window.

---

### 12. RMD (Denied — Age 61, Rule Starts at 73)

```
Process my required minimum distribution
```

Rule 6 fires: `rmd_required=False` → **RMD_NOT_YET_REQUIRED**

Gabriel is 61. RMD kicks in at age 73 under SECURE 2.0. In ~12 years this path would open.

---
---

## PART-009 — Daniela Reyes · Capital One · Loan Cap Demo

**Profile:** Age 41 · $100k vested · 100% vesting · 10yr service · 1 active loan ($22k balance, $25k high in last 12 months) · not HCE · not RMD
**Max additional loan:** $25,000 — min($50k − $25k prior high, 50% × $100k) = min($25k, $50k)
**PLAN-003 allows up to 2 outstanding loans** — she has 1, so a 2nd is eligible
**Current deferral:** 8% pre-tax · emp YTD $12,000 · er YTD $5,000
**Funds:** 70% COF-SP500 · 30% COF-STABLE

### Action Summary

| # | Action | Status | Result |
|---|---|---|---|
| 1 | Loan $30k — over cap | ✅ DENIES | LOAN_CAP_EXCEEDED |
| 2 | Loan $20k — allowed | ✅ WORKS | supervised |
| 3 | Loan $25k — at max | ✅ WORKS | supervised (exact cap) |
| 4 | Deferral change | ✅ WORKS | full or supervised |
| 5 | Hardship | ✅ WORKS | human_review |
| 6 | Investment reallocation | ✅ WORKS | full autonomy |
| 7 | Beneficiary update | ✅ WORKS | human_review |
| 8 | Address update | ✅ WORKS | full autonomy |
| 9 | In-service distribution | ✅ DENIES | IN_SERVICE_AGE_NOT_MET (age 41) |
| 10 | Separation distribution | ✅ DENIES | SEPARATION_STATUS_INVALID (active) |
| 11 | QDRO | ✅ WORKS | human_review |
| 12 | RMD | ✅ DENIES | RMD_NOT_YET_REQUIRED |

---

### 1. Loan $30k — Over Cap (Best Denial Demo)

```
I want to borrow $30,000
```

- IRC §72(p) formula: min($50k − $25k prior, 50% × $100k) = $25k max
- $30k > $25k → **LOAN_CAP_EXCEEDED**
- FAP rule output: "Maximum allowed: $25,000 (IRC §72(p)). Existing highest balance in last 12 months: $25,000."

**What to point out:** FAP computed the prior loan balance from the participant record and applied the two-part IRC §72(p) formula. Neither the LLM nor the participant knew what the cap was — FAP enforced it automatically.

---

### 2. Loan $20k — Approved (Second Loan Allowed)

```
I want to take out a second loan for $20,000 over 3 years
```

- $20k ≤ $25k headroom ✓
- 2 outstanding loans permitted by PLAN-003 · currently 1 → allowed ✓
- Rule 12: **supervised**

Confirm panel. Confirm to execute.

---

### 3. Loan $25k — Exactly at Cap

```
I want to borrow $25,000
```

- $25k = $25k max exactly ✓
- Rule 12: **supervised**

This is a good demo of the formula being precise — one dollar over fails, exactly at the cap passes.

---

### 4. Deferral Change

```
Change my deferral to 10% pre-tax
```

- 10% × $88k = $8,800 projected — under $23k ✓
- Rule 12: **full** (increase, not stopping)

```
Set my deferral to 0%
```

Rule 12: **supervised** (stopping contributions).

---

### 5. Hardship — Prevent Eviction

```
I need $6,000 for rent — I've received an eviction notice
```

- Rule 6: `prevent_eviction` = valid safe harbor expense in PLAN-003 ✓
- Rule 12: **human_review**

Variations that also work: `I need help with tuition` · `funeral expenses` · `primary home purchase` · `FEMA disaster relief`

---

### 6. Investment Reallocation

Current: 70% COF-SP500 · 30% COF-STABLE

```
Reallocate to 50% COF-SP500, 30% COF-BOND, 20% COF-INTL
```

Full autonomy. Executes immediately.

---

### 7. Beneficiary Update

```
Add my son Marco Reyes as 50% beneficiary alongside my current beneficiary
```

Approved with condition (no spousal consent provided) · **human_review**

---

### 8. Address Update

```
Update my address to 201 W Lake St, Chicago, IL 60606
```

Full autonomy.

---

### 9. In-Service Distribution (Denied)

```
I'd like to withdraw from my account while still employed
```

Rule 6 fires: age 41 < 59½ → **IN_SERVICE_AGE_NOT_MET**

---

### 10. Separation Distribution (Denied)

```
I left my job — can I take my balance out?
```

Rule 6 fires: status = `active` → **SEPARATION_STATUS_INVALID**

(If Daniela were actually terminated, this would open. She'd get her full vested balance since vesting = 100%.)

---

### 11. QDRO

```
Process a QDRO. Participant: Daniela Reyes. Alternate payee: Carlos Reyes.
Plan: Capital One Associate Savings Plan. Amount: 30% of vested balance.
Payment period: as a lump sum at earliest retirement age.
```

Rule 12: **human_review** · queued for sponsor.

---

### 12. RMD (Denied)

```
I need to take my required minimum distribution
```

Rule 6 fires: not RMD age → **RMD_NOT_YET_REQUIRED**

---
---

## PART-007 — Yuki Tanaka · Prudential · Unvested Cliff

**Profile:** Age 31 · $38k vested · **0% employer vesting** (3-yr cliff, only 1.5yr service) · no loans · not HCE · not RMD
**Max loan:** $19,000 — min($50k − $0, 50% × $38k) ← vested balance is the binding constraint
**PLAN-004 allows max 1 outstanding loan** — none currently, so 1 allowed
**Current deferral:** 4% pre-tax · emp YTD $4,000 · er YTD $4,000
**Funds:** 100% PESP-GOALMAKER-MOD
**Plan:** PLAN-004 Prudential · not safe harbor · 3-yr cliff vesting

### Action Summary

| # | Action | Status | Result |
|---|---|---|---|
| 1 | Loan $15k — approved | ✅ WORKS | supervised |
| 2 | Loan $25k — over cap | ✅ DENIES | LOAN_CAP_EXCEEDED (50% of $38k = $19k max) |
| 3 | Deferral change | ✅ WORKS | full or supervised |
| 4 | Hardship | ✅ WORKS | human_review |
| 5 | Investment reallocation | ✅ WORKS | full autonomy · PESP funds |
| 6 | Beneficiary update | ✅ WORKS | human_review |
| 7 | Address update | ✅ WORKS | full autonomy |
| 8 | In-service distribution | ✅ DENIES | IN_SERVICE_AGE_NOT_MET (age 31) |
| 9 | Separation distribution | ✅ DENIES | SEPARATION_STATUS_INVALID (active) |
| 10 | QDRO | ✅ WORKS | human_review |
| 11 | RMD | ✅ DENIES | RMD_NOT_YET_REQUIRED |

---

### 1. Loan $15k — Approved (Prudential Plan)

```
I want to take out a $15,000 loan over 5 years
```

- Rule 6: $15k ≤ $19k headroom ✓ · PLAN-004 loans permitted ✓ · 0 outstanding < 1 limit ✓
- Rule 12: **supervised**

**What to point out:** Yuki has 0% employer vesting, but vesting does NOT block loans — it only limits distributions of the employer match. Her full vested_balance ($38k) is her own employee contributions, which are always 100% vested. The loan cap is based on that amount.

---

### 2. Loan $25k — Over Cap

```
I want to borrow $25,000
```

- IRC §72(p): min($50k, 50% × $38k) = **$19k max**
- $25k > $19k → **LOAN_CAP_EXCEEDED**

This shows the formula binding on the 50%-of-balance constraint rather than the $50k IRS cap (which is the typical binding constraint for larger accounts).

---

### 3. Deferral Change

```
Change my deferral to 6% pre-tax
```

- 6% × $72k = $4,320 — well under limits ✓
- Rule 12: **full**

Variations:
```
Increase my contributions to 10% pre-tax
```
```
Set my deferral to 0%
```
(0% → supervised)

---

### 4. Hardship Distribution (Prudential Plan)

```
I need $3,000 for medical bills
```

- PLAN-004 has safe harbor hardship standard · same qualifying expenses as PLAN-003
- Rule 12: **human_review**

Note: Since PLAN-004 is not safe harbor for employer contributions, hardship approval involves additional documentation scrutiny during sponsor review.

---

### 5. Investment Reallocation — Prudential Funds

Current: 100% PESP-GOALMAKER-MOD

```
Reallocate to 70% PESP-GOALMAKER-AGG and 30% PESP-SP500
```

Full autonomy. Prudential fund IDs: `PESP-SP500`, `PESP-BOND`, `PESP-STABLE`, `PESP-INTL`, `PESP-SMIDCAP`, `PESP-PRU-STOCK`, `PESP-GOALMAKER-AGG`, `PESP-GOALMAKER-MOD`, `PESP-GOALMAKER-CONS`

```
Move everything to the PESP-GOALMAKER-AGG fund
```

```
Split 60% PESP-GOALMAKER-MOD and 40% PESP-SP500
```

---

### 6. Beneficiary Update

```
Set my beneficiary to my mother Keiko Tanaka
```

Approved with condition (no spousal consent provided) · **human_review**

---

### 7. Address Update

```
Update my address to 88 West 3rd St, San Francisco, CA 94107
```

Full autonomy.

---

### 8. In-Service Distribution (Denied)

```
I want to make an in-service withdrawal
```

Rule 6 fires: age 31 < 59½ → **IN_SERVICE_AGE_NOT_MET**

---

### 9. Separation Distribution (Denied — Active Employee + Vesting Cliff Explainer)

```
I quit last week — can I take my 401k balance?
```

Rule 6 fires: status = `active` → **SEPARATION_STATUS_INVALID**

**What WOULD happen at termination (educate the lead):** If Yuki actually terminated with 1.5yr service under PLAN-004's 3-yr cliff: she would be entitled to take only her **employee contributions** (always 100% vested). The employer match ($4,000 YTD) would be **forfeited** back to the plan. This is the cliff vesting rule — before 3 years, 0% of employer match is owned. After 3 years, 100% is owned. There is no in-between (cliff, not graduated).

---

### 10. QDRO

```
Process a QDRO. Participant: Yuki Tanaka. Alternate payee: Hiroshi Tanaka.
Plan: The Prudential Employee Savings Plan. Amount: 25% of vested balance.
Payment period: during accumulation phase.
```

Rule 12: **human_review** · queued.

---

### 11. RMD (Denied)

```
I need to process my required minimum distribution
```

Rule 6 fires: **RMD_NOT_YET_REQUIRED** (age 31)

---
---

## Plan Sponsor Scenarios (All Participants)

### Queue Approval Flow (after any human_review action)

**For hardship and QDRO (document-gated — 3-step sponsor process):**
1. Run `hardship` or `qdro` as a participant — crew runs, request queued
2. CLI prompts for document upload — pick sample doc or enter file path
3. LLM verifies document automatically
4. Switch roles: `back` → Plan Sponsor → pick the plan
5. `queue` — see entry with `📎 1 doc  (LLM verified · awaiting your review)`
6. `docs <entry_id>` — read document content, LLM note, see "Awaiting your approval"
7. `approve doc <entry_id>` — explicitly approve the document → "Document approved"
8. `Approve <entry_id> — valid documentation received` — approve the request
9. `queue` — confirm it's gone
10. `audit` — see the FAP decision

**If participant skipped document upload:**
- Sponsor sees `⚠ no documents uploaded`
- `Approve <ID>` → blocked: shows 3-step instructions

**If sponsor tries to approve request before running `approve doc`:**
- Blocked: "Cannot approve — documents not yet reviewed"
- Shows: Step 1: docs · Step 2: approve doc · Step 3: Approve

**For other human_review actions (beneficiary_update, in_service_distribution):**
1. Run the action as a participant
2. No document prompt (no doc requirement for these)
3. Switch to sponsor → `queue` → `Approve <ID> — reason`

### Blackout Management

**Activate:**
```
Activate a blackout from 2026-08-01 to 2026-09-01 for recordkeeper transition to Empower
```

**Test it:** switch to any Participant → try any write action → Rule 2 fires: **BLACKOUT_ACTIVE**. Reads still work (balance, investments, etc.).

**Deactivate:**
```
Deactivate the blackout
```

Or via natural language:
```
End the blackout period
```

### Audit Log

```
audit
```

Shows last 10 FAP decisions — approved and denied. Every entry includes: timestamp · participant · action · rule result · ERISA citation. ERISA §107 requires 6-year retention.

### LLM Sponsor Actions (Complex Queries)

These go through CrewAI (not instant):
```
What does PLAN-003 allow for in-service distributions?
```
```
Explain the hardship standards for Capital One participants
```
```
What are the loan repayment terms for our plan?
```

---
---

## What's Not Testable with Current Demo Data

| Scenario | Why Not Available | What to Say |
|---|---|---|
| Separation distribution — approved | No terminated/retired participant in DB | "In production, a terminated Daniela with status=terminated would qualify for a full rollover distribution" |
| RMD — approved | No participant with `rmd_required=True` in DB | "Gabriel at age 73 would trigger this path; FAP checks rmd_required, rmd_notice_issued, and rmd_amount_current_year" |
| Vesting cliff denial for distributions | No terminated < 3yr participant in DB | "If Yuki terminated today she'd keep employee contributions only — employer match ($4k) forfeited at cliff" |
| Rollover in | No rollover_in endpoint yet (Phase 4) | "PLAP verifies the plan accepts rollovers; PAAP writes the deposit; FAP token required" |
| Second hardship after suspension | No hardship on record for any participant | "After a safe harbor hardship, PLAN-003 imposes a 6-month contribution suspension; FAP Rule 6 enforces it" |

---

## Automated Test Suite

```bash
# No API key needed — pure Python
pytest tests/ -v
```

87 tests · every rule has pass AND fail coverage · zero stubs — every rule actually evaluates.

---

## Key Phrases for the Presentation

- "LLM interprets intent, Python enforces compliance — they never cross."
- "FAP issues a cryptographically signed JWT. PAAP will not write a single byte without it."
- "Every approval and denial is immutably logged for ERISA §107 six-year retention."
- "The supervised confirm/cancel flow is pure Python — confirming a loan costs zero API calls."
- "We implemented the SECURE 2.0 Roth catch-up rule on the day it became effective — January 1, 2026."
- "The compliance engine is 100% testable without an API key — 87 tests, zero stubs."
- "The sponsor queue survives process restarts. The sponsor can approve the next morning and the audit trail is intact."
