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

## Notes

- Gabriel (PART-006): vested $210k, deferral 10% pre-tax, plan PLAN-003
- Daniela (PART-009): already has a $22k outstanding loan (LOAN-0100) — her loan headroom will be lower
- If you reset demo state first (sponsor portal → Reset Demo), balances restore to seed values
- Fast mode uses Haiku (~3-5 sec). Toggle to 🤖 CrewAI to compare response time (~2-3 min)
