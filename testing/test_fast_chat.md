# Fast Chat — Demo Scenarios

All actions go through `POST /chat/fast` → Haiku classifier → PAAP → PLAP → FAP (12 rules) → execute or queue.

---

## Demo Participants

| Name | ID | DOB | Age | Status | Vested Balance | Active Loans |
|---|---|---|---|---|---|---|
| Gabriel Stone | PART-006 | 1964-04-15 | ~62 | active | $200,000 | 1 (limits headroom) |
| Yuki Tanaka | PART-007 | 1994-12-05 | ~31 | active | $38,000 | 0 |
| Amara Osei | PART-008 | 1990-02-18 | ~36 | active | $85,000 | 0 |
| Daniela Reyes | PART-009 | 1985-09-14 | ~40 | active | $100,000 | 1 ($22k outstanding) |

Plans: PLAN-003 (Gabriel, Amara, Daniela) · PLAN-004 (Yuki)
Login credentials: participant ID + last name (e.g. PART-008 / Osei)

---

## 1. Loan Initiation

**Autonomy: `supervised`** — FAP approves, participant must confirm, then provide bank details.

### 1a. Happy path — Amara requests a loan
```
"I'd like to borrow $10,000 for general purpose, repay over 5 years"
```
Expected: FAP approves → `supervised` → Confirm button appears → bank details card.

### 1b. Missing params — collect step by step
```
"I want a loan"
→ "How much would you like to borrow?"
"$8,000"
→ "How many years would you like to repay over?"
"4 years"
→ "Is this for a general purpose or primary residence?"
"general"
→ FAP runs → supervised flow
```

### 1c. Denial — Gabriel's loan exceeds IRC §72(p) cap
Gabriel already has a loan. The $50k cap minus his highest balance reduces his headroom.
```
"I need $50,000 loan for general purpose, 5 years"
```
Expected: FAP denies with `LOAN_CAP_EXCEEDED` — Haiku explains the limit.

### 1d. Denial — Yuki requests primary residence loan but repayment exceeds 5-year limit
```
"I want a $15,000 loan for general use, repay in 6 years"
```
Expected: FAP denies with `LOAN_REPAYMENT_PERIOD_EXCEEDED` (general purpose max is 5 years).

### 1e. Primary residence — allowed up to 30 years
```
"I want a $15,000 loan to buy my primary home, repay in 10 years"
```
Expected: FAP approves → supervised.

---

## 2. Hardship Distribution

**Autonomy: `human_review`** — queued for sponsor approval + document upload required before sponsor can approve.

### 2a. Happy path — valid IRS category
```
"I need $5,000 for medical bills"
```
Expected: FAP approves → human_review → document upload card (medical_bill).

### 2b. Any expense type passes through for FAP to decide
```
"I need $3,000 for a vacation"
"I need $1,000 for car repairs"
```
Expected: FAP runs Rule 6 `_check_hardship_rules` → denies with `HARDSHIP_EXPENSE_NOT_QUALIFIED`.
Haiku explains which expense types are valid.

### 2c. Multi-turn — missing amount
```
"I need help with a hardship withdrawal"
→ "How much do you need for the hardship distribution?"
"$4,500 for eviction prevention"
→ FAP runs → human_review → document upload card (eviction_notice)
```

### 2d. Document upload flow
After human_review response, document upload card appears.
- Pick: Medical bill / Eviction notice / Tuition invoice / Funeral invoice
- Upload a file from data/sample_docs/ (e.g. medical_bill.txt)
- LLM (Haiku) verifies: doc type valid for expense type, content matches, name on doc must match participant
- If name on doc is wrong (e.g. Gabriel's doc uploaded from Amara's account) → `verified=false`

### 2e. Sponsor approval flow
1. Log in as sponsor (PLAN-003 / sponsor PIN)
2. Review queue → see hardship entry
3. `docs <entry_id>` → view uploaded doc
4. Approve docs → then Approve request → disbursement to bank

---

## 3. Deferral Change

**Autonomy: `full`** (increase) or **`supervised`** (decrease to 0%).

### 3a. Increase deferral — full autonomy, executes immediately
```
"Change my deferral to 8%"
"Increase my contribution to 10%"
```
Expected: FAP approves → `full` → writes to DB immediately — no confirm needed.

### 3b. Decrease to zero — supervised
```
"Stop my contributions, set deferral to 0%"
```
Expected: FAP approves → `supervised` → confirm button appears. On confirm: executes.

### 3c. Catch-up — Gabriel (age 62) can contribute catch-up
Gabriel is 60–63, so he qualifies for SECURE 2.0 enhanced catch-up ($10k limit).
```
"I want to set my deferral to 12% with catch-up"
```
Expected: FAP approves with enhanced catch-up.

### 3d. Denial — over annual limit
```
"Set my deferral to 50%"
```
Expected: if contributions YTD are already near the 402(g) limit, FAP denies.

---

## 4. Investment Reallocation

**Autonomy: `full`** — executes immediately if rebalancing to a QDIA fund, supervised otherwise.

### 4a. Check current investments
```
"What am I invested in?"
"Show me my current fund holdings"
```
Expected: data question → returns investment elections with fund names and percentages.

### 4b. Check available funds
```
"What funds are available in my plan?"
"Show me the fund lineup"
```
Expected: data question → returns plan's full fund lineup.

### 4c. Reallocation via structured UI (investment page)
Not through chat — use the Investments page in the portal.
Select funds → set percentages → submit → PAAP executes → balances update.

---

## 5. In-Service Distribution

**Autonomy: `human_review`** — only for active employees age 59½+. All others denied by FAP.

### 5a. Happy path — Gabriel (age 62, active, PLAN-003 allows it)
```
"I'd like to take $10,000 out of my account while I'm still working"
"I want an in-service withdrawal of $15,000"
"I'm 62 and want to withdraw $20,000"
```
Expected: FAP approves (age ≥ 59.5, plan allows) → `human_review` → queued for sponsor.
No document upload required — sponsor just reviews and approves.

### 5b. Denial — Amara (age 36, too young)
```
"I want to take $5,000 out while I'm still employed"
```
Expected: FAP denies `IN_SERVICE_AGE_NOT_MET` — "In-service distributions require age 59½. Your current age is 36.4."

### 5c. Denial — Yuki (age 31, too young)
```
"I want an in-service withdrawal of $3,000"
```
Expected: FAP denies — too young.

### 5d. Denial — Daniela (age 40, too young)
Same — denied.

> **Demo tip:** Use Gabriel for the success scenario, Amara for the denial scenario.

---

## 6. Separation Distribution

**Autonomy: `human_review`** — but only if employment status is `terminated` or `retired`.
All demo participants are `active` → this always results in a FAP denial with demo data.

### 6a. Denial — all participants are active employees
```
"I left my job and want to take $20,000 out"
"I retired and want my money — $50,000 separation distribution"
"I quit last month, can I withdraw $30,000?"
```
Expected: FAP denies `SEPARATION_STATUS_INVALID` — "employment_status must be terminated or retired."

> **Demo tip:** This demonstrates the compliance engine correctly blocking a distribution the participant can't take yet. Explain to reviewers: "In a real deployment, the recordkeeper would update employment_status to 'terminated' when the participant leaves. FAP automatically unblocks at that point."

---

## 7. RMD (Required Minimum Distribution)

**Autonomy: `human_review`** — but only if `rmd_required=True` on participant record.
No demo participant has reached RMD age (youngest qualifying age is 73) → always denied.

### 7a. Denial — not yet required (all participants)
```
"I need to take my RMD this year"
"Process my required minimum distribution"
"I have to take money out this year — mandatory withdrawal"
```
Expected: FAP denies `RMD_NOT_YET_REQUIRED` — "Participant has not yet reached the required minimum distribution age."

> **Demo tip:** Gabriel (born 1964, age 62) is closest — he'll reach RMD age at 73 in 2037.
> This scenario shows FAP preventing an RMD that isn't required yet — protecting against early taxation.

---

## 8. QDRO (Qualified Domestic Relations Order)

**Autonomy: `human_review`** — court-ordered transfer to alternate payee (e.g. ex-spouse). Document upload required.

### 8a. Happy path — Amara, 50% to ex-spouse
```
"I need to set up a QDRO, 50% to my ex-wife Jane Smith"
"QDRO transfer, 40% to Robert Osei"
"Divorce settlement — transfer 50% of my account to Jane Smith"
```
Expected: FAP approves (PAAP auto-fills participant_name, plan_name, payment_period) → `human_review` → queued + document upload card.
Upload: `data/sample_docs/qdro_court_order.txt`

### 8b. Missing params — step by step
```
"I need a QDRO"
→ "What is the full name of the alternate payee?"
"Jane Smith"
→ "What percentage of your vested balance should be transferred?"
"50"
→ FAP runs → human_review
```

### 8c. Daniela, 30% to ex-partner
```
"Court-ordered transfer — 30% to Carlos Reyes"
```
Expected: FAP approves → human_review → document upload.

> **Note:** PAAP automatically enriches the payload with participant_name, plan_name, benefit_amount_or_pct, and payment_period before FAP runs. The participant only needs to specify alternate_payee_name and transfer_pct.

---

## 9. Beneficiary Update

**Autonomy: `human_review`** — queued for sponsor confirmation. No document upload required.

### 9a. Happy path — Amara adds spouse as beneficiary
```
"Change my beneficiary to my husband James Osei"
"Update my beneficiary to Maria Chen, she's my child"
"Designate my sister Priya as my beneficiary"
```
Expected: FAP approves (spousal consent flagged as condition but passes to human_review) → queued.
Sponsor sees entry in review queue and approves.

### 9b. Missing params — step by step
```
"I want to update my beneficiary"
→ "What is the full name of your beneficiary?"
"Maria Chen"
→ "What is their relationship to you? (spouse, child, parent, sibling, estate, or other)"
"child"
→ FAP runs → human_review
```

### 9c. Multiple beneficiaries — allocation
```
"Add my spouse John as 60% beneficiary and my son Mike as 40%"
```
Expected: classifier extracts beneficiary_name, relationship, allocation_pct for the primary.
(Multi-beneficiary in one message may require two separate requests in current implementation.)

> **Note:** PLAN-003 requires spousal consent — FAP passes with a condition "human review required." The sponsor verifies consent documentation offline.

---

## 10. Data Questions

No transaction — Haiku fetches and formats account data.

### 10a. Balance
```
"What is my balance?"
"How much do I have in my 401k?"
```

### 10b. Loan headroom
```
"How much can I borrow?"
"What's my loan limit?"
```

### 10c. My investments
```
"What am I invested in?"
"Show me my current funds and percentages"
"Where is my money invested?"
```

### 10d. Vesting
```
"What is my vesting percentage?"
"Am I fully vested?"
```

### 10e. RMD info
```
"When do I have to start taking RMDs?"
"Tell me about my required minimum distribution"
```

### 10f. Distribution options
```
"What withdrawal options do I have?"
```

### 10g. Conceptual questions
```
"What is vesting?"
"How do RMDs work?"
"What is an ERISA fiduciary?"
"What is a QDRO?"
"Explain the 402(g) limit"
```

---

## 11. Sponsor Actions

Log in as: plan_sponsor / PLAN-003

### 11a. View review queue
- Portal: Review Queue tab
- See all pending entries: hardship, in-service, QDRO, beneficiary, etc.

### 11b. Approve a disbursement entry (hardship, in-service, QDRO)
1. View entry → check documents uploaded (for hardship/QDRO: document required)
2. Approve docs → then Approve entry
3. Participant then submits bank details → funds disburse

### 11c. Approve a non-disbursement entry (beneficiary update)
1. View entry
2. Approve → status updates immediately

### 11d. Deny any entry
Enter a denial note → participant is notified.

### 11e. Manage blackout
```
POST /admin/blackout
{ "activate": true, "reason": "Annual recordkeeper switch", "start_date": "2026-08-01", "end_date": "2026-08-31" }
```
While blackout is active: all participant writes fail with `BLACKOUT_PERIOD_ACTIVE`.

### 11f. Audit log
```
GET /admin/audit
```
Every FAP decision (approved and denied) with ERISA citation and timestamp.

---

## 12. Full End-to-End Demo Script (8 minutes)

**Step 1 — Login as Amara Osei (PART-008)**

**Step 2 — Check balance and investments**
```
"What's my balance and what am I invested in?"
```

**Step 3 — Request a loan (supervised flow)**
```
"I'd like to borrow $15,000 for general purpose, repay in 4 years"
```
Confirm → bank details → done.

**Step 4 — Change deferral (full autonomy)**
```
"Increase my contributions to 8%"
```
Executes immediately.

**Step 5 — Request hardship (human_review + document)**
```
"I need $4,000 for medical bills"
```
Upload `medical_bill.txt` from sample_docs → LLM verifies → queued.

**Step 6 — Request QDRO (human_review + document)**
```
"QDRO — 50% to Jane Smith"
```
Upload `qdro_court_order.txt` → queued.

**Step 7 — Update beneficiary (human_review, no doc)**
```
"Change my beneficiary to my daughter Maria, she's my child"
```
Queued.

**Step 8 — Switch to Gabriel Stone (PART-006)**

**Step 9 — In-service distribution (passes — he's 62)**
```
"I'd like to take $10,000 out while I'm still working"
```
Queued for sponsor.

**Step 10 — Show FAP denial — Gabriel requests RMD**
```
"I need to take my required minimum distribution"
```
Denied — not yet required. Shows compliance engine working.

**Step 11 — Login as plan_sponsor**
- Review queue: 4 entries from Amara, 1 from Gabriel
- Approve Amara's hardship (docs already verified)
- Approve Gabriel's in-service
- Deny Amara's QDRO with note "Awaiting court filing confirmation"

**Step 12 — Audit log**
- Show full FAP audit trail with ERISA citations
