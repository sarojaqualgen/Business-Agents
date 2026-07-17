# Fast Chat Testing Guide

Make sure the chat is in **⚡ Fast** mode (toggle in top-right of chat header).
Login as any participant — Gabriel (PART-006) is good for most tests.

---

## 1. Loan — all params in one message (should execute immediately)

```
I want to take a loan of $5000 for 3 years for general purposes
```
**Expect:** Haiku replies confirming the loan is approved, confirm/cancel dialog appears.

```
Can I borrow $10000 for 5 years, general loan
```
**Expect:** Same — approved, confirm dialog.

---

## 2. Loan — missing params (multi-turn, Haiku asks one question at a time)

**Turn 1:**
```
I want a loan
```
**Expect:** Asks "How much would you like to borrow?"

**Turn 2:**
```
$8000
```
**Expect:** Asks "How many years would you like to repay over?"

**Turn 3:**
```
5 years
```
**Expect:** Asks "Is this for a general purpose or primary residence?"

**Turn 4:**
```
general
```
**Expect:** Loan approved, confirm dialog appears.

---

## 3. Loan — with extra context in the message (Haiku should ignore the story)

```
My car broke down last month and I really need help, can I please borrow $7000 for 4 years for general purposes?
```
**Expect:** Extracts $7000, 4 years, general — ignores car story. Confirm dialog appears.

---

## 4. Loan — should be denied by FAP (use Gabriel PART-006, vested balance ~$210k)

```
I want to borrow $200000 for 5 years for general purposes
```
**Expect:** FAP denies — loan exceeds IRC §72(p) cap ($50k or 50% of vested). Haiku explains the denial in plain English.

```
I want to borrow $50000 for 5 years for general purposes
```
**Expect:** This should pass for Gabriel (vested $210k, headroom $50k). Confirm dialog appears.

---

## 5. Data questions — Haiku fetches real data from PAAP/PLAP

```
What is my vested balance?
```
**Expect:** Haiku shows the real vested balance from the DB.

```
How much can I borrow?
```
**Expect:** Shows the IRC §72(p) loan headroom figure.

```
Am I vested? How many years of service do I have?
```
**Expect:** Vesting percentage and years of service from DB.

```
Does my plan allow hardship withdrawals?
```
**Expect:** Pulls plan capabilities — yes/no with details.

```
What funds can I invest in?
```
**Expect:** Lists the fund lineup for Gabriel's plan.

---

## 6. Conceptual questions — Haiku answers from knowledge + rule context

```
What is vesting?
```
**Expect:** Plain English explanation of vesting.

```
What is an RMD?
```
**Expect:** Explains Required Minimum Distributions.

```
What are the 12 rules you check before approving anything?
```
**Expect:** Lists all 12 FAP rules in plain English.

```
What is Rule 7?
```
**Expect:** Explains the IRC §72(p) loan cap rule.

```
What is SECURE 2.0 and what does it change?
```
**Expect:** Explains SECURE 2.0 catch-up and Roth HCE requirement.

```
What does supervised autonomy mean?
```
**Expect:** Explains the confirmation flow.

---

## 7. Mixed — question + loan in same message

```
How much can I borrow and can I take a $5000 loan for 3 years general?
```
**Expect:** Haiku answers the headroom question AND triggers the loan approval flow.

---

## 8. Unknown / off-topic — should redirect politely

```
What's the weather today?
```
**Expect:** Polite redirect to 401k topics.

```
Tell me a joke
```
**Expect:** Polite redirect.

---

## 9. Confirm / cancel flow (after any loan approval)

After the confirm dialog appears:
- Click **Confirm** → should trigger bank details card (loans are disbursements)
- Fill in routing + account number → submit → loan recorded

OR:
- Click **Cancel** → loan cancelled, no execution

---

---

## 10. Hardship — all params in one message (should queue for sponsor review)

Login as **Amara (PART-008)** or **Gabriel (PART-006)** — both are on PLAN-003 which allows all 7 IRS hardship categories.

```
I need $3000 for medical bills
```
**Expect:** Haiku extracts amount=$3000, expense=medical. FAP passes → queued for sponsor review. Reply says it needs sponsor approval and to upload supporting docs. **Document upload card appears.**

```
I need a hardship withdrawal of $5000 for tuition
```
**Expect:** Same flow — queued, upload card appears.

```
I have an eviction notice and need $4500
```
**Expect:** Haiku maps "eviction notice" → prevent_eviction. Queued, upload card appears.

```
I need $2000 for funeral expenses for my mother
```
**Expect:** Haiku maps "funeral expenses" → funeral. Queued, upload card appears.

```
I want to buy my first home and need $10000
```
**Expect:** Haiku maps "buy my first home" → primary_home_purchase. Queued, upload card appears.

---

## 11. Hardship — missing params (multi-turn)

**Turn 1:**
```
I need a hardship withdrawal
```
**Expect:** Asks "How much do you need for the hardship distribution?"

**Turn 2:**
```
$6000
```
**Expect:** Asks "What is the reason for your hardship? Options: medical expenses, tuition, home purchase, eviction prevention, funeral costs, casualty loss, or FEMA disaster."

**Turn 3:**
```
medical
```
**Expect:** FAP passes → queued for sponsor review. Document upload card appears.

---

## 12. Hardship — natural language mapping (Haiku should translate correctly)

These all have amount + natural language expense type:

```
I have hospital bills totaling $8000
```
**Expect:** expense → medical. Queued.

```
My landlord is evicting me and I need $3500
```
**Expect:** expense → prevent_eviction. Queued.

```
I need to pay college tuition of $7000
```
**Expect:** expense → tuition. Queued.

```
My house burned down in a disaster — I need $5000
```
**Expect:** expense → casualty_loss or FEMA_disaster. Queued.

---

## 13. Hardship — FAP denial scenarios

```
I need $3000 for a vacation
```
**Expect:** Haiku extracts expense="vacation" which is not a recognized IRS hardship category. FAP denies with HARDSHIP_CRITERIA_NOT_MET. Haiku explains in plain English that vacation is not a qualifying expense.

```
I need $1000 for car repairs
```
**Expect:** FAP denies — car repairs are not a qualifying hardship expense. Explanation given.

---

## 14. Hardship — document upload flow (after queue)

After the document upload card appears (from any test above):

**Step 1 — upload a matching doc:**
- Select expense type (pre-filled if Haiku extracted it)
- Select document type (e.g. "Medical Bill" for medical expense)
- Upload `data/sample_docs/medical_bill.txt`
- Click **Upload & Verify Document**
- **Expect:** Green "Verified" badge. Shows verification note + key details (amount, date, provider).

**Step 2 — upload wrong doc type for the expense:**
- Select expense type = "Tuition"
- Select document type = "Eviction Notice"
- Upload `data/sample_docs/eviction_notice.txt`
- **Expect:** Yellow "Needs Review" badge. Haiku notes the mismatch between document type and claimed expense.

**Step 3 — upload someone else's document:**
- Upload a sample doc with a different name on it (e.g. medical_bill.txt has "Metro General Hospital" patient name)
- **Expect:** If patient name on document doesn't match logged-in participant's name → "Needs Review" + name mismatch warning shown.

**Step 4 — dismiss upload and skip:**
- Click X on the upload card
- **Expect:** Upload card dismissed. Request is still queued — participant can upload later from Documents page.

---

## 15. Hardship — sponsor review flow (switch to sponsor portal)

After a hardship is queued and a document is uploaded:

**As sponsor:**
1. Go to **Review Queue**
2. Find the hardship entry — should show `hardship_distribution`, participant name, amount, expense type
3. Click to expand → see uploaded document + verification status
4. If no verified doc is uploaded → **Approve button is blocked** (ERISA requirement)
5. Once a verified doc exists → Approve button unlocks
6. Click **Approve** → status changes to `approved_awaiting_bank_details`

**Back as participant:**
7. Go to participant chat or dashboard
8. Submit bank details (routing + account number) via the disburse flow
9. **Expect:** Funds recorded, vested balance decremented, loan record created

**Deny scenario:**
- Sponsor clicks **Deny** with a reason
- **Expect:** Entry marked denied. Participant sees denial.

---

## 16. Hardship — mixed question + hardship in same message

```
Does my plan allow hardship withdrawals and I need $4000 for medical bills
```
**Expect:** Haiku answers the plan capabilities question AND queues the hardship. Both the data answer AND the upload card appear.

---

## Notes

- Gabriel (PART-006): vested $210k, deferral 10% pre-tax, plan PLAN-003 (Capital One)
- Amara (PART-008): primary demo participant, plan PLAN-003 — best for hardship testing
- Daniela (PART-009): already has a $22k outstanding loan (LOAN-0100) — her loan headroom will be lower
- Yuki (PART-007): plan PLAN-004 (Prudential) — also allows all 7 hardship categories
- Both PLAN-003 and PLAN-004 support all 7 IRS safe harbor hardship expense types: medical, tuition, primary_home_purchase, prevent_eviction, funeral, casualty_loss, FEMA_disaster
- Sample docs are in `data/sample_docs/` — medical_bill.txt, eviction_notice.txt, tuition_invoice.txt, funeral_invoice.txt
- Hardship always routes to `human_review` — no immediate execution, sponsor must approve first
- If you reset demo state first (sponsor portal → Reset Demo), balances restore to seed values
- Fast mode uses Haiku (~3-5 sec). Toggle to 🤖 CrewAI to compare response time (~2-3 min)
