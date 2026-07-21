# Fast Chat — Testing Scenarios

**Flow:** `POST /chat/fast` → Haiku classifier → PAAP (loads participant + plan) → FAP (12 ERISA rules) → execute / queue / deny

---

## Reference: Participants

| ID | Name | Age | Status | Vested | Total | Deferral | Active Loans | Loan Headroom | Plan |
|---|---|---|---|---|---|---|---|---|---|
| PART-006 | Gabriel Stone | 62.3 | active | $200,000 | $225,000 | 10% | 1 ($10k outstanding) | **$40,000** | PLAN-003 |
| PART-007 | Yuki Tanaka | 31.6 | active | $38,000 | $42,000 | 4% | 0 | **$19,000** | PLAN-004 |
| PART-008 | Amara Osei | 36.4 | active | $85,000 | $92,000 | 6% | 0 | **$42,500** | PLAN-003 |
| PART-009 | Daniela Reyes | 40.8 | active | $100,000 | $105,000 | 8% | 1 ($22k outstanding, highest $25k) | **$25,000** | PLAN-003 |

Login: participant ID as username, last name as password (e.g. `PART-008` / `Osei`).

**Loan headroom formula (IRC §72(p)):** `min( $50,000 − highest loan balance last 12 months, 50% of vested balance )`
- Gabriel: min($50k − $10k, $100k) = **$40k**
- Yuki: min($50k − $0, $19k) = **$19k** ← 50% vested is the binding cap
- Amara: min($50k − $0, $42.5k) = **$42.5k** ← 50% vested is the binding cap
- Daniela: min($50k − $25k, $50k) = **$25k** ← highest-balance cap

---

## Reference: Plans

| | PLAN-003 (Capital One) | PLAN-004 (Prudential PESP) |
|---|---|---|
| Participants | Gabriel, Amara, Daniela | Yuki |
| Eligibility | Age 18, immediate | Age 21, 12 months service |
| Employer match | 100% on first 3% + 50% on next 3% | 100% on first 4% |
| Vesting | 2-year cliff | 3-year cliff |
| Max loan | $50k or 50% vested, up to 2 loans | $50k or 50% vested, 1 loan |
| General loan repayment | 5 years max | 5 years max |
| Primary residence loan | 15 years max (5+10 extension) | 20 years max (5+15 extension) |
| Hardship | Permitted (safe harbor, no 6-month suspension) | Permitted |
| In-service at 59½ | **Yes** | **Yes** |
| Normal retirement age | 65 | 65 |

---

## Reference: Sample Documents

All files are in `data/sample_docs/`. Name on document must match the logged-in participant.

| File | Participant Named | Use For |
|---|---|---|
| `medical_bill.txt` | Amara Osei | Hardship — medical |
| `eviction_notice.txt` | Amara Osei | Hardship — prevent_eviction |
| `tuition_invoice.txt` | Amara Osei Jr. | Hardship — tuition |
| `funeral_invoice.txt` | (check file) | Hardship — funeral |
| `qdro_court_order.txt` | Amara Osei (Petitioner) | QDRO |
| `gabriel_medical_bill.pdf` | Gabriel Stone | Hardship — medical (Gabriel's account) |
| `gabriel_tuition_invoice.pdf` | Gabriel Stone | Hardship — tuition (Gabriel's account) |

**Name-match rule:** LLM verifies the name on the uploaded document matches the logged-in participant. If names differ → `verified=false`, sponsor cannot approve.

---

## 1. Loan Initiation

**Autonomy: `supervised`** — FAP approves → confirm button → bank details card → executes
**FAP Rule:** Rule 4 (Vesting), Rule 6 (Loan Cap §72(p)), Rule 7 (Repayment Period)

---

### 1a. Happy path — Amara borrows within headroom
**Login:** Amara Osei (PART-008)
```
"I'd like to borrow $20,000 for general purpose, repay over 4 years"
```
Expected: FAP approves → `supervised` → confirm button → bank details card.
Max allowed: $42,500 general, 5 yr repayment. $20k / 4yr is within limits.

---

### 1b. Happy path — Daniela at her exact cap
**Login:** Daniela Reyes (PART-009)
```
"I need a $25,000 loan for general purpose, 5 years"
```
Expected: FAP approves at exact §72(p) cap → `supervised`.

---

### 1c. Happy path — Gabriel, primary residence loan
**Login:** Gabriel Stone (PART-006)
```
"I want a $30,000 loan to buy my primary home, repay over 10 years"
```
Expected: FAP approves (primary residence extension allows up to 15 years) → `supervised`.

---

### 1d. Happy path — Yuki, small loan at 50%-vested cap
**Login:** Yuki Tanaka (PART-007)
```
"I want to borrow $15,000 for general purpose, 3 years"
```
Expected: FAP approves ($15k < $19k headroom) → `supervised`.

---

### 1e. Multi-turn — missing params collected one at a time
**Login:** Any participant
```
Turn 1: "I want a loan"
         → "How much would you like to borrow?"
Turn 2: "$10,000"
         → "How many years would you like to repay over?"
Turn 3: "3 years"
         → "Is this for a general purpose or a primary residence purchase?"
Turn 4: "general"
         → FAP runs → supervised
```

---

### 1f. Denial — exceeds §72(p) cap (Gabriel)
**Login:** Gabriel Stone (PART-006) — headroom is $40k
```
"I need $45,000 loan for general purpose, 5 years"
```
Expected: FAP Rule 6 denies `LOAN_CAP_EXCEEDED`.
Message: "The maximum you can borrow is $40,000 based on your current loan balance and IRC §72(p) limits."

---

### 1g. Denial — exceeds §72(p) cap (Daniela)
**Login:** Daniela Reyes (PART-009) — headroom is $25k
```
"I want a $30,000 loan for general use, 4 years"
```
Expected: FAP Rule 6 denies `LOAN_CAP_EXCEEDED`. Max allowed: $25,000.

---

### 1h. Denial — repayment period too long (general)
**Login:** Amara Osei (PART-008)
```
"I want a $10,000 loan for general use, repay in 6 years"
```
Expected: FAP Rule 7 denies `LOAN_REPAYMENT_PERIOD_EXCEEDED`. General max is 5 years.

---

### 1i. Denial — repayment too long even for primary residence
**Login:** Amara Osei (PART-008)
```
"I want a $10,000 loan to buy my primary home, repay in 20 years"
```
Expected: FAP denies — PLAN-003 primary residence max is 15 years. (PLAN-004 allows 20.)

---

## 2. Hardship Distribution

**Autonomy: `human_review`** — queued for sponsor + document upload required before sponsor can approve
**FAP Rule:** Rule 6 (`_check_hardship_rules`) → checks qualifying_expense_type

Valid IRS expense categories: `medical`, `tuition`, `primary_home_purchase`, `prevent_eviction`, `funeral`, `casualty_loss`, `FEMA_disaster`

---

### 2a. Happy path — Amara, medical
**Login:** Amara Osei (PART-008)
```
"I need $4,000 for medical bills"
"I have hospital bills — I need $2,500"
"Medical expenses — I need $6,000"
```
Expected: FAP approves → `human_review` → queued → document upload card appears.
Upload: `medical_bill.txt` — named Amara Osei, matches account → `verified=true`.

---

### 2b. Happy path — Amara, eviction prevention
**Login:** Amara Osei (PART-008)
```
"I'm about to be evicted, I need $5,700"
"I need help with rent — $4,000 to prevent eviction"
```
Expected: FAP approves → `human_review`.
Upload: `eviction_notice.txt` — named Amara Osei → `verified=true`.

---

### 2c. Happy path — Amara, tuition
**Login:** Amara Osei (PART-008)
```
"I need $8,000 for college tuition"
"I have a tuition invoice — I need $8,198"
```
Expected: FAP approves → `human_review`.
Upload: `tuition_invoice.txt` — named Amara Osei Jr. → name mismatch → `verified=false` (sponsor blocked until correct doc uploaded).

---

### 2d. Happy path — Amara, funeral
**Login:** Amara Osei (PART-008)
```
"I need $5,000 for funeral expenses"
```
Expected: FAP approves → `human_review`.
Upload: `funeral_invoice.txt` → verify name matches.

---

### 2e. Denial — invalid expense type passes through, FAP rejects
**Login:** Any participant
```
"I need $3,000 for a vacation"
"I need $1,000 for car repairs"
"I need $2,000 to pay off my credit card"
"I need money for a new laptop"
```
Expected: classifier still sets intent=`hardship_distribution` (any reason), FAP Rule 6 denies `HARDSHIP_EXPENSE_NOT_QUALIFIED`.
Haiku explains the 7 valid IRS categories.

---

### 2f. Multi-turn — missing amount
**Login:** Amara Osei (PART-008)
```
Turn 1: "I need a hardship withdrawal"
         → "How much do you need for the hardship distribution?"
Turn 2: "What are my options?"
         → "What is the reason for your hardship? Options: medical expenses,
            tuition, home purchase, eviction prevention, funeral costs,
            casualty loss, or FEMA disaster."
Turn 3: "$3,000 for medical"
         → FAP runs → human_review
```

---

### 2g. Wrong document — name mismatch (cross-account)
**Login:** Gabriel Stone (PART-006)
```
"I need $3,000 for medical bills"
```
Upload: `medical_bill.txt` (named Amara Osei, not Gabriel)
Expected: LLM name-match check fails → `verified=false` → "Name on document does not match account holder."
Sponsor **cannot** approve until a verified document is on file.
Correct upload: `gabriel_medical_bill.pdf` (named Gabriel Stone) → `verified=true`.

---

### 2h. Sponsor approval flow
1. Login as plan_sponsor (PLAN-003)
2. Review Queue → find hardship entry
3. View entry docs → confirm `verified=true`
4. Approve docs → Approve entry
5. Status changes to `approved_awaiting_bank_details`
6. Participant logs back in → bank details card → submits routing/account → funds disburse

---

## 3. Deferral Change

**Autonomy:** `full` for increases (executes immediately), `supervised` for decrease to 0%
**FAP Rule:** Rule 5 (§402(g) contribution limits), Rule 12 (autonomy level assignment)

---

### 3a. Full autonomy — increase deferral
**Login:** Amara Osei (PART-008) — currently at 6%
```
"Change my deferral to 8%"
"Increase my contributions to 10%"
"Set my 401k contribution to 12%"
```
Expected: FAP approves → `full` → executes immediately, DB updated, no confirm needed.

---

### 3b. Supervised — decrease to zero
**Login:** Any participant
```
"Stop my contributions, set deferral to 0%"
"I want to pause my 401k contributions"
```
Expected: FAP approves → `supervised` → confirm button. On confirm: deferral set to 0%, DB updated.

---

### 3c. Supervised — loan deferral trigger
**Login:** Any participant
```
"Reduce my contributions to 2%"
```
Expected: FAP approves → `supervised` (below normal threshold). Confirm required.

---

### 3d. Catch-up contribution — Gabriel (age 60–63, SECURE 2.0)
**Login:** Gabriel Stone (PART-006) — age 62.3, qualifies for enhanced catch-up
```
"I want to maximize my catch-up contributions"
"Set my deferral to 15% with catch-up enabled"
```
Expected: FAP Rule 5 allows enhanced catch-up limit ($10,000 additional, IRC §414(v) SECURE 2.0).

---

### 3e. Type switch — Roth vs pre-tax
**Login:** Any participant
```
"Switch my contributions to Roth"
"Change my deferral to 8% Roth"
```
Expected: FAP approves → `full` → deferral_type updated to `roth`.

---

## 4. Investment Reallocation

**Autonomy: `full`** — executes immediately (PAAP writes elections to DB)
Not via chat — done through the portal Investments page.

---

### 4a. Chat — check current holdings
**Login:** Any participant
```
"What am I invested in?"
"Show me my current fund allocations"
"Where is my 401k money invested right now?"
```
Expected: data question → Haiku returns investment_elections with fund_id and allocation_pct.

**Amara's holdings (PLAN-003):**
- COF-LIFEPATH-2040: 70%
- COF-SP500: 30%

**Gabriel's holdings (PLAN-003):**
- COF-SP500: 70%
- COF-STABLE: 30%

---

### 4b. Chat — check available funds
**Login:** Any participant
```
"What funds does my plan offer?"
"Show me the fund lineup"
"What can I invest in?"
```
Expected: data question → returns PLAN-003 or PLAN-004 fund lineup.

---

### 4c. Portal reallocation — happy path
1. Login as Amara → Investments tab
2. Current: 70% COF-LIFEPATH-2040, 30% COF-SP500
3. Change to: 50% COF-LIFEPATH-2040, 30% COF-SP500, 20% COF-STABLE
4. Submit → PAAP executes → elections update immediately

---

### 4d. Portal reallocation — invalid (percentages don't sum to 100%)
1. Set 40% + 40% = 80%
2. Submit → frontend validation blocks before API call

---

## 5. In-Service Distribution

**Autonomy: `human_review`** — queued for sponsor, no document upload required
**FAP Rule:** Rule 6 (`_check_in_service_rules`) — age ≥ 59.5 AND plan must allow it
PLAN-003 and PLAN-004 both allow in-service at 59½.

---

### 5a. Happy path — Gabriel (age 62.3, qualifies)
**Login:** Gabriel Stone (PART-006)
```
"I'd like to take $10,000 out of my account while I'm still working"
"I want an in-service withdrawal of $20,000"
"I'm 62 and want to withdraw some money while employed"
"Take $15,000 from my 401k — I'm still working"
```
Expected: FAP approves (age 62.3 ≥ 59.5, plan allows) → `human_review` → queued.
Sponsor approves (no doc required) → participant provides bank details → disburse.

---

### 5b. Denial — Amara (age 36.4, too young)
**Login:** Amara Osei (PART-008)
```
"I want to take $5,000 out while I'm still employed"
"In-service withdrawal of $10,000"
"I want to withdraw money from my 401k while I'm working"
```
Expected: FAP Rule 6 denies `IN_SERVICE_AGE_NOT_MET`.
Message: "In-service distributions require age 59½. Your current age is 36.4."

---

### 5c. Denial — Yuki (age 31.6, too young)
**Login:** Yuki Tanaka (PART-007)
```
"I want an in-service withdrawal of $3,000"
"Take $5,000 from my plan while I'm working"
```
Expected: FAP denies `IN_SERVICE_AGE_NOT_MET`. Age 31.6, need 59.5.

---

### 5d. Denial — Daniela (age 40.8, too young)
**Login:** Daniela Reyes (PART-009)
```
"I want to withdraw $8,000 in-service"
```
Expected: FAP denies `IN_SERVICE_AGE_NOT_MET`. Age 40.8, need 59.5.

> **Demo tip:** Gabriel is the only participant who passes. Use Amara for the denial side-by-side comparison.

---

## 6. Separation Distribution

**Autonomy: `human_review`** — BUT requires `employment_status = terminated or retired`
**FAP Rule:** Rule 6 (`_check_separation_rules`)

All demo participants have `employment_status = active` → **always denied with current data.**

---

### 6a. Denial — all participants are active employees
**Login:** Any participant
```
"I left my job and want to take $20,000 out"
"I retired — I want my separation distribution of $50,000"
"I quit last month, can I withdraw $30,000?"
"I'm terminating employment and want my full balance"
```
Expected: FAP Rule 6 denies `SEPARATION_STATUS_INVALID`.
Message: "Separation distributions require employment status of 'terminated' or 'retired'. Current status: 'active'."

> **What this demonstrates:** The compliance engine blocks distributions that participants cannot legally take yet. When the recordkeeper updates employment_status to 'terminated' after an actual separation, FAP automatically unblocks. Additionally, FAP requires `rollover_402f_notice_confirmed=True` (IRC §402 rollover notice must be sent 30–180 days before distribution) — even for terminated employees, this notice step must happen first.

---

## 7. RMD (Required Minimum Distribution)

**Autonomy: `human_review`** — BUT requires `rmd_required = True` on participant record
**FAP Rule:** Rule 6 (`_check_rmd_rules`) — also requires `rmd_notice_issued=True` in payload

No demo participant has reached age 73 → **always denied with current data.**
Gabriel is closest: DOB 1964-04-15, will reach RMD age in 2037.

---

### 7a. Denial — not yet required (all participants)
**Login:** Any participant
```
"I need to take my RMD this year"
"Process my required minimum distribution"
"I have to take money out — mandatory withdrawal"
"What is my RMD amount?"
```
Expected: FAP Rule 6 denies `RMD_NOT_YET_REQUIRED`.
Message: "Participant has not yet reached the required minimum distribution age."

> **What this demonstrates:** FAP prevents participants from processing an RMD before age 73 — protecting them from unnecessary taxation.

---

### 7b. Chat data question — RMD info
**Login:** Any participant
```
"When do I have to start taking RMDs?"
"Tell me about required minimum distributions"
"What is the RMD age?"
```
Expected: data question, not a transaction → Haiku explains RMD rules (age 73, IRC §401(a)(9)).

---

## 8. QDRO (Qualified Domestic Relations Order)

**Autonomy: `human_review`** — queued for sponsor + document upload required (court order)
**FAP Rule:** Rule 8 (anti-alienation exception for QDRO), Rule 6 (`_check_qdro_rules`)
**PAAP auto-fills:** `participant_name` (DB lookup), `plan_name`, `benefit_amount_or_pct`, `payment_period=lump_sum`

---

### 8a. Happy path — Amara, 50% to ex-spouse Jane Smith
**Login:** Amara Osei (PART-008)
```
"I need to set up a QDRO, 50% to my ex-wife Jane Smith"
"QDRO — transfer 50% of my account to Jane Smith"
"Divorce settlement — 50% goes to Jane Smith via QDRO"
```
Expected: PAAP enriches payload → FAP approves → `human_review` → queued → document upload card.
Upload: `qdro_court_order.txt` (Petitioner: Amara Osei) → `verified=true`.
Sponsor approves docs → approves entry → Amara provides bank details → funds split.

---

### 8b. Happy path — Daniela, 30% to ex-partner Carlos Reyes
**Login:** Daniela Reyes (PART-009)
```
"Court-ordered transfer — 30% to Carlos Reyes"
"QDRO for my divorce — 30% to Carlos Reyes"
```
Expected: FAP approves → `human_review`.
Note: `transfer_pct=30` → PAAP computes `amount = $100,000 × 30% = $30,000` at execution time.

---

### 8c. Missing params — step by step
**Login:** Any participant
```
Turn 1: "I need a QDRO"
         → "What is the full name of the alternate payee?"
Turn 2: "Jane Smith"
         → "What percentage of your vested balance should be transferred (e.g. 50 for 50%)?"
Turn 3: "50"
         → FAP runs → human_review
```

---

### 8d. Different language triggers correctly
**Login:** Any participant
```
"My divorce decree requires me to transfer half my 401k to my ex"
"Qualified domestic relations order for my ex-wife, 40% please"
"Court order to split my retirement account — transfer to Robert Osei"
```
Expected: classifier maps to `qdro`, asks for missing payee name or percentage.

---

## 9. Beneficiary Update

**Autonomy: `human_review`** — queued for sponsor, no document upload required
**FAP Rule:** Rule 6 (`_check_beneficiary_rules`) — PLAN-003 requires spousal consent (QJSA), passes with condition

---

### 9a. Happy path — Amara designates spouse
**Login:** Amara Osei (PART-008)
```
"Change my beneficiary to my husband James Osei"
"Update my beneficiary — James Osei, spouse"
```
Expected: FAP passes with condition "spousal consent status not confirmed — human review required" → `human_review` → queued.
Sponsor reviews and approves (verifies spousal consent offline).

---

### 9b. Happy path — Amara designates child
**Login:** Amara Osei (PART-008)
```
"Update my beneficiary to Maria Chen, she's my child"
"My daughter Maria Chen should be my beneficiary"
"Designate Maria Chen (child) as my 401k beneficiary"
```
Expected: FAP approves → `human_review` → queued.

---

### 9c. Happy path — Gabriel designates sibling
**Login:** Gabriel Stone (PART-006)
```
"Change my beneficiary to my brother David Stone, he's my sibling"
"Set David Stone as my beneficiary — relationship is sibling"
```
Expected: FAP approves → `human_review` → queued.

---

### 9d. Missing params — step by step
**Login:** Any participant
```
Turn 1: "I want to update my beneficiary"
         → "What is the full name of your beneficiary?"
Turn 2: "Maria Chen"
         → "What is their relationship to you? (spouse, child, parent, sibling, estate, or other)"
Turn 3: "my daughter"
         → Haiku maps "my daughter" → child → FAP runs → human_review
```

---

### 9e. Multiple beneficiaries — separate requests
**Login:** Any participant
```
Request 1: "Add my spouse John as beneficiary, 60% allocation"
Request 2: "Also add my son Mike as beneficiary, 40% allocation"
```
Note: Current implementation handles one beneficiary per request. Two separate chat turns create two queue entries; sponsor approves both.

---

## 10. Data Questions (no transaction)

Haiku fetches real data from PAAP/PLAP and formats a plain-English response.

---

### 10a. Account balance
```
"What is my balance?"
"How much do I have in my 401k?"
"Show me my account summary"
```
Expected: returns `total_balance`, `vested_balance`, `vesting_percentage`.

---

### 10b. Loan headroom
```
"How much can I borrow?"
"What's my maximum loan amount?"
"What is my loan limit?"
```
Expected: returns `max_additional_loan_amount` with §72(p) explanation.
- Amara: $42,500
- Gabriel: $40,000
- Daniela: $25,000
- Yuki: $19,000

---

### 10c. My current investments
```
"What am I invested in?"
"Show me my current funds and percentages"
"Where is my money invested right now?"
"What are my holdings?"
```
Expected: returns `investment_elections` — fund IDs with allocation percentages.

---

### 10d. Available fund lineup (plan-level)
```
"What funds are available in my plan?"
"Show me the fund lineup"
"What can I invest in?"
"What investment options does my plan offer?"
```
Expected: returns the plan's full fund lineup, not personal holdings.

---

### 10e. Vesting status
```
"What is my vesting percentage?"
"Am I fully vested?"
"How many years until I'm vested?"
```
Expected: returns `vesting_percentage`, `years_of_vesting_service`.
- Gabriel, Amara, Daniela: 100% vested (PLAN-003, 2yr cliff, all have 2+ years)
- Yuki: depends on years of service (PLAN-004, 3yr cliff)

---

### 10f. RMD info (data question, not transaction)
```
"When do I have to start taking RMDs?"
"Tell me about required minimum distributions"
"What is the RMD age for my plan?"
```
Expected: Haiku explains RMD rules — age 73, IRC §401(a)(9), plan-specific start rule.

---

### 10g. Distribution options
```
"What withdrawal options do I have?"
"What distributions can I take from my plan?"
```
Expected: returns available distribution types based on plan and participant status.

---

### 10h. Plan capabilities
```
"What does my plan allow?"
"Does my plan have loans?"
"Can I do a hardship withdrawal?"
```
Expected: returns plan capabilities — loans, hardship, in-service, etc.

---

### 10i. Conceptual questions (no data fetch)
```
"What is vesting?"
"How do RMDs work?"
"What is an ERISA fiduciary?"
"What is a QDRO?"
"Explain the 402(g) limit"
"What is safe harbor hardship?"
"What is catch-up contribution?"
"What is a blackout period?"
"How does the IRC §72(p) loan cap work?"
```
Expected: Haiku answers using FAP_RULES_TEXT context — no DB call.

---

### 10j. Combined question + transaction in one message
```
"What's my balance and I'd also like to request a $10,000 loan for 3 years general"
"Tell me my loan limit and take a hardship withdrawal of $3,000 for medical"
```
Expected: both handled in same response — data answer first, then transaction result.

---

## 11. Sponsor Actions

**Login:** plan_sponsor / PLAN-003

---

### 11a. View review queue
Portal: Review Queue tab → see all pending entries with action type, participant name, amount, created date.

---

### 11b. Approve disbursement entry (hardship, in-service, QDRO)
1. Click entry → view details
2. For hardship/QDRO: check Documents tab — must have at least one `verified=true` doc
3. Approve docs (marks docs sponsor-approved)
4. Approve entry → status → `approved_awaiting_bank_details`
5. Participant receives notification → submits bank details → funds disburse

Approve blocked if: no verified document on file for hardship or QDRO entries.

---

### 11c. Approve non-disbursement entry (beneficiary update)
1. View entry
2. No document required
3. Approve → status → `approved` immediately

---

### 11d. Deny any entry
Enter a denial reason (required) → status → `denied`.
Participant sees denial note in their queue.

---

### 11e. Activate blackout period
```
POST /admin/blackout
{
  "activate": true,
  "reason": "Annual recordkeeper transition to Empower",
  "start_date": "2026-08-01",
  "end_date": "2026-08-31"
}
```
While active: all participant writes (loans, hardship, deferral changes) fail with `BLACKOUT_PERIOD_ACTIVE` (FAP Rule 2).
Reads (balance, fund lineup, data questions) still work.

---

### 11f. Lift blackout
```
POST /admin/blackout
{ "activate": false }
```

---

### 11g. Audit log
`GET /admin/audit` — every FAP decision (approved AND denied) with:
- timestamp, participant_id, agent_id, action, authorized (bool)
- denial_code, denial_reason, erisa_citation
- autonomy_level (for approved)

ERISA §107 requires 6-year retention. DOL can subpoena the log.

---

## 12. FAP Denial Reference

| Action | Trigger | Denial Code | FAP Rule |
|---|---|---|---|
| Loan | Amount > §72(p) cap | `LOAN_CAP_EXCEEDED` | Rule 6 |
| Loan | Repayment > plan max | `LOAN_REPAYMENT_PERIOD_EXCEEDED` | Rule 6 |
| Loan | Plan disallows loans | `LOAN_NOT_PERMITTED` | Rule 6 |
| Hardship | Invalid expense type | `HARDSHIP_EXPENSE_NOT_QUALIFIED` | Rule 6 |
| Hardship | Plan disallows hardship | `HARDSHIP_NOT_PERMITTED` | Rule 6 |
| In-service | Age < 59.5 | `IN_SERVICE_AGE_NOT_MET` | Rule 6 |
| In-service | Plan disallows it | `IN_SERVICE_AGE_NOT_MET` | Rule 6 |
| Separation | Status not terminated/retired | `SEPARATION_STATUS_INVALID` | Rule 6 |
| RMD | `rmd_required=False` | `RMD_NOT_YET_REQUIRED` | Rule 6 |
| RMD | Notice not sent | `RMD_NOTICE_NOT_ISSUED` | Rule 6 |
| QDRO | Missing required fields | `QDRO_FIELDS_MISSING` | Rule 6 |
| Beneficiary | Spousal consent refused | `QJSA_CONSENT_REQUIRED` | Rule 6 |
| Any | Blackout active | `BLACKOUT_PERIOD_ACTIVE` | Rule 2 |
| Any | Participant not eligible | `PARTICIPATION_NOT_MET` | Rule 3 |
| Any | Agent not registered | `AGENT_NOT_REGISTERED` | Rule 1 |
| Any write | Unvested employer match | `VESTING_NOT_MET` | Rule 4 |

---

## 13. End-to-End Demo Script (10 minutes)

### Step 1 — Login as Amara Osei (PART-008, PLAN-003)

### Step 2 — Data questions
```
"What's my balance and what am I invested in?"
```
Shows: $85,000 vested, $92,000 total. Invested: 70% COF-LIFEPATH-2040, 30% COF-SP500.

### Step 3 — Loan request (supervised flow)
```
"I'd like to borrow $15,000 for general purpose, repay in 4 years"
```
FAP approves → confirm button → bank details card → loan executes.
Balance updates immediately.

### Step 4 — Deferral increase (full autonomy — no confirm)
```
"Increase my contributions to 8%"
```
FAP approves → executes immediately → deferral updated from 6% to 8%.

### Step 5 — Hardship with document (human_review)
```
"I need $4,000 for medical bills"
```
FAP approves → `human_review` → document upload card.
Upload `medical_bill.txt` → LLM verifies name matches (Amara Osei) → `verified=true` → queued.

### Step 6 — QDRO with court order (human_review)
```
"I need to set up a QDRO — 50% to Jane Smith"
```
FAP approves → queued → document upload card.
Upload `qdro_court_order.txt` → `verified=true` → queued.

### Step 7 — Beneficiary update (human_review, no doc)
```
"Change my beneficiary to my daughter Maria, she's my child"
```
FAP approves → `human_review` → queued. No document needed.

### Step 8 — Show denial — invalid hardship reason
```
"I need $2,000 for a vacation"
```
FAP Rule 6 denies `HARDSHIP_EXPENSE_NOT_QUALIFIED`. Compliance engine working.

### Step 9 — Switch to Gabriel Stone (PART-006)

### Step 10 — In-service distribution (passes — age 62.3)
```
"I'd like to take $10,000 out while I'm still working"
```
FAP approves (age ≥ 59.5, plan allows) → `human_review` → queued.

### Step 11 — Show denial — Gabriel tries RMD (not yet required)
```
"I need to take my required minimum distribution"
```
FAP Rule 6 denies `RMD_NOT_YET_REQUIRED`. Gabriel is 62 — RMD starts at 73.

### Step 12 — Show denial — Amara tries in-service (too young)
**Switch back to Amara**
```
"I want to take $5,000 out while I'm still working"
```
FAP Rule 6 denies `IN_SERVICE_AGE_NOT_MET`. Age 36.4 < 59.5.

### Step 13 — Login as plan_sponsor (PLAN-003)

### Step 14 — Review queue
Five entries: Amara's hardship, QDRO, beneficiary + Gabriel's in-service.

### Step 15 — Approve Amara's hardship
Docs tab → `verified=true` → Approve docs → Approve entry.
Amara gets notified → provides bank details → disburse.

### Step 16 — Approve Gabriel's in-service distribution
No doc required → Approve directly.

### Step 17 — Deny Amara's QDRO
Enter note: "Awaiting certified court filing — resubmit with stamped order."

### Step 18 — Audit log
Show full compliance trail — every FAP decision with ERISA citation, timestamp, and result.
