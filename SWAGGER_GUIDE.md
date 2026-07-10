# Aldergate API — Swagger Testing Guide

How to test every endpoint at `http://localhost:8000/docs` before the UI is ready.

---

## Starting the Server

```bash
cd /Users/devanshsaroja/Documents/a-Devolopment/ERISA/project
source .venv/bin/activate
uvicorn api.main:app --reload --port 8000
```

Open `http://localhost:8000/docs` in your browser.

---

## How Swagger Works

Every endpoint has a **Try it out** button. Click it, fill in the values, click **Execute**. The response appears below.

The page is divided into sections:
- **Auth** — login, get your session token
- **Meta** — lookup participants, plans, actions (no login needed)
- **Chat** — send a message, get streaming response
- **Transactions** — confirm or cancel a supervised (loan) transaction
- **Documents** — upload supporting docs for hardship / QDRO
- **Queue** — sponsor views and approves/denies requests
- **Admin** — audit log, blackout management
- **Health** — server status check

---

## Step 1 — Login and Authorize (do every session)

**Find:** `POST /auth/login` → click → **Try it out**

### Login as Participant
```json
{
  "principal_type": "participant",
  "participant_id": "PART-008",
  "plan_id": "PLAN-003"
}
```

### Login as Plan Sponsor
```json
{
  "principal_type": "plan_sponsor",
  "plan_id": "PLAN-003"
}
```

### Login as Investment Advisor
```json
{
  "principal_type": "investment_advisor",
  "participant_id": "PART-008",
  "plan_id": "PLAN-003"
}
```

**After executing:** Copy the `session_token` value from the response.

**Then:** Click the **Authorize 🔒** button at the very top of the page.
Type `Bearer ` (with a space) then paste your token. Click **Authorize**.

> Every endpoint from this point onwards will automatically send your token.
> You must re-authorize if you switch roles (participant ↔ sponsor).

---

## Step 2 — Check Available Participants and Plans

No login needed for these.

**`GET /meta/participants`** → Try it out → Execute

Shows all 4 demo participants:

| ID | Who | Good for |
|---|---|---|
| PART-006 | Gabriel Stone, age 61 | Catch-up contributions, in-service distribution |
| PART-007 | Yuki Tanaka, age 31, 1.5yr service | Eligibility denial demo |
| PART-008 | Amara Osei, age 36 | Main demo — all scenarios |
| PART-009 | Daniela Reyes, existing $25k loan | Loan cap denial demo |

**`GET /meta/plans`** → Try it out → Execute

| ID | Plan |
|---|---|
| PLAN-003 | Capital One Financial Corporation Associate Savings Plan |
| PLAN-004 | The Prudential Employee Savings Plan (PESP) |

**`GET /meta/actions`** → Try it out → Execute

Shows all valid actions with example messages you can paste into `/chat`.

---

## Step 3 — Chat

Login as **participant** first (Step 1).

**`POST /chat`** → Try it out → paste message → Execute

The response will be a stream of lines. Each line starts with `data:` followed by a JSON event.

### Event types you'll see:

| Type | What it means |
|---|---|
| `agent_start` | An agent began working — show in thinking block |
| `tool_use` | Agent called a tool (e.g. GetPlanRules) |
| `tool_result` | Tool returned data |
| `step_done` | Agent finished a task — summary inside |
| `response` | **The final answer** — show this as the chat bubble |
| `done` | Stream complete |
| `error` | Something went wrong |

### Example messages to try:

**Loan — supervised (needs confirm step after):**
```json
{ "message": "I want to take a loan of $10,000 for 5 years" }
```

**Hardship — human review (goes to sponsor queue):**
```json
{ "message": "I need a hardship withdrawal of $5,000 for medical expenses" }
```

**Deferral change — executes immediately:**
```json
{ "message": "Change my deferral to 8%" }
```

**Investment rebalance — executes immediately:**
```json
{ "message": "Put 60% in FIDELITY-500 and 40% in VANGUARD-TDF-2040" }
```

**Just a question — no transaction:**
```json
{ "message": "How much can I borrow?" }
```
```json
{ "message": "What is my current vesting percentage?" }
```

**Address update — executes immediately:**
```json
{ "message": "Update my address to 123 Main St, Chicago IL 60601" }
```

**QDRO — goes to sponsor queue:**
```json
{ "message": "QDRO — Participant: Amara Osei, Alternate payee: James Osei, Plan: Capital One 401k, Amount: 50% of vested balance, Payment period: lump sum" }
```

---

## Step 4 — Confirm a Loan (Supervised Flow)

After sending the loan message in Step 3, the transaction is **waiting for your confirmation**. It has NOT executed yet.

**Check what is pending:**

`GET /transactions/pending` → Try it out → Execute

You will see:
```json
{
  "has_pending": true,
  "action": "loan_initiation",
  "requires_bank_details": true,
  "summary": {
    "amount": 10000,
    "repayment_years": 5,
    "purpose": "general purpose",
    "warning": "This loan reduces your retirement savings and accrues interest."
  },
  "message": "FAP approved this transaction. All 12 ERISA rules passed. Your explicit confirmation is required."
}
```

**Step 4a — Confirm the loan:**

`POST /transactions/confirm` → Try it out → Execute (no body needed)

Because `loan_initiation` disburses funds, the response will be:
```json
{
  "status": "awaiting_bank_details",
  "action": "loan_initiation",
  "message": "Transaction confirmed. Please provide your bank details to receive the funds."
}
```

> Non-disbursement supervised actions (e.g. deferral to 0%) skip the bank details step and execute immediately with `"status": "executed"`.

**Step 4b — Provide bank details to disburse funds:**

`POST /transactions/disburse` → Try it out → body:
```json
{
  "routing_number": "021000021",
  "account_number": "123456789",
  "account_type": "checking"
}
```

Response:
```json
{
  "status": "executed",
  "disbursement": {
    "routing_number": "021000021",
    "account_last4": "6789",
    "account_type": "checking",
    "status": "initiated",
    "estimated_arrival": "3–5 business days"
  }
}
```

Bank details are used once and **never stored**.

**To cancel before confirming:**

`POST /transactions/cancel` → Try it out → Execute (no body needed)

Response will say `"status": "cancelled"`.

> If `has_pending` is false, either the transaction already executed (full autonomy) or it was sent to the sponsor queue (human_review). Only supervised actions need confirm/cancel/disburse.

---

## Step 5 — Upload a Document (Hardship / QDRO)

After submitting a hardship or QDRO request via `/chat`, you need to upload a supporting document. The sponsor cannot approve until you do.

### Step 5a — Get the queue entry ID

You need the `entry_id` from the queue. Either:
- Check the `response` event from the `/chat` stream — the entry ID is mentioned in the text
- Or login as sponsor and call `GET /queue` (Step 6a below) and copy the `entry_id`

### Step 5b — Upload the document

**`POST /documents/upload`** → Try it out

This is a form upload, not JSON. Fill in each field:

| Field | Value for medical hardship | Value for QDRO |
|---|---|---|
| `queue_entry_id` | paste entry ID from queue | paste entry ID from queue |
| `action_type` | `hardship_distribution` | `qdro` |
| `expense_type` | `medical` | `qdro` |
| `doc_type` | `medical_bill` | `court_order` |
| `file` | upload `data/sample_docs/medical_bill.txt` | upload `data/sample_docs/qdro_court_order.txt` |

**For the file field:** Click **Choose File** → navigate to your project folder → `data/sample_docs/` → pick the file.

**Click Execute.**

The response stream shows the Document Verification Agent working. Look for the `response` event — it tells you:
- Whether the document was verified (passed / needs review)
- The document ID
- Key details found (amount, date, provider)

### Supported file types: `.txt` `.pdf` `.docx`

### Expense type → document to upload mapping:

| Expense type | `doc_type` value | Sample file |
|---|---|---|
| `medical` | `medical_bill` | `medical_bill.txt` |
| `prevent_eviction` | `eviction_notice` | `eviction_notice.txt` |
| `tuition` | `tuition_invoice` | `tuition_invoice.txt` |
| `funeral` | `funeral_invoice` | `funeral_invoice.txt` |
| `qdro` | `court_order` | `qdro_court_order.txt` |

---

## Step 6 — Sponsor Queue (Approve / Deny)

**Re-login as sponsor** — go back to `POST /auth/login`, use the sponsor payload, copy new token, re-authorize.

### Step 6a — See all pending requests

`GET /queue` → Try it out → Execute

Copy the `entry_id` of the request you want to act on.

### Step 6b — See uploaded documents

`GET /queue/{entry_id}/docs` → Try it out → fill in `entry_id` → Execute

Shows all documents the participant uploaded, with LLM verification result and preview.

### Step 6c — Approve the documents (required for hardship and QDRO)

`POST /queue/{entry_id}/approve-docs` → Try it out → fill in `entry_id` → body:
```json
{ "note": "Documents reviewed and verified" }
```

> You must do this before approving the request. If you skip it, the approve call will return an error.

### Step 6d — Approve the request

`POST /queue/{entry_id}/approve` → Try it out → fill in `entry_id` → body:
```json
{ "note": "Approved — all documentation in order" }
```

**For disbursement actions (hardship, in-service distribution)** the response will be:
```json
{
  "status": "approved_awaiting_bank_details",
  "entry_id": "AB12CD34",
  "message": "Approved. Participant must now provide bank details via POST /transactions/disburse to receive funds."
}
```

The request stays in `approved_awaiting_bank_details` status until the participant provides bank details.

**Step 6d-ii — Participant provides bank details (re-login as participant first):**

`POST /transactions/disburse` → body:
```json
{
  "routing_number": "021000021",
  "account_number": "123456789",
  "account_type": "checking",
  "entry_id": "AB12CD34"
}
```

Include the `entry_id` from the queue entry. The funds will be disbursed and the queue entry moves to `approved`.

---

### What If the Participant Comes Back the Next Day? (FAP Token Expired)

The FAP token issued at approval time has a 24-hour TTL. If the participant
does not provide bank details within 24 hours of the sponsor approving, the
token expires and `/transactions/disburse` returns:

```json
{ "detail": "FAP token validation failed: Token has expired." }
```

The queue entry stays at `approved_awaiting_bank_details` — it is NOT stuck.
The sponsor simply approves again to re-issue a fresh token. No re-review needed.

**Step 1 — Sponsor calls approve again (re-login as sponsor):**

`POST /queue/{entry_id}/approve` → same body as before:
```json
{ "note": "Re-issuing token — participant missed the window" }
```

Because the entry is already `approved_awaiting_bank_details` (not `pending`),
the system skips the full approval flow and only re-issues the FAP token:

```json
{
  "status": "approved_awaiting_bank_details",
  "entry_id": "AB12CD34",
  "message": "Token re-issued. Participant has a fresh 24-hour window to provide bank details via POST /transactions/disburse."
}
```

**Step 2 — Participant calls disburse again (re-login as participant):**

`POST /transactions/disburse` → same body with `entry_id`:
```json
{
  "routing_number": "021000021",
  "account_number": "123456789",
  "account_type": "checking",
  "entry_id": "AB12CD34"
}
```

Fresh token is valid → transaction executes → entry moves to `approved`.

> The sponsor does not need to re-check documents or re-review the request.
> Calling approve on an `approved_awaiting_bank_details` entry only re-issues
> the token — the approval decision itself does not change.

---

### Step 6e — Deny the request

`POST /queue/{entry_id}/deny` → Try it out → fill in `entry_id` → body:
```json
{ "note": "Insufficient documentation provided" }
```

---

## Step 7 — Admin (Sponsor Only)

### View FAP audit log

`GET /admin/audit` → Try it out → Execute

Shows every compliance decision (approved and denied) with rule details.

> Note: Audit log is in-memory only until Phase 6 (PostgreSQL). It resets when the server restarts.

### Manage blackout period

`POST /admin/blackout` → Try it out → body (natural language, goes through SponsorCrew):
```json
{ "message": "Activate a blackout from 2026-08-15 to 2026-09-01 for recordkeeper transition" }
```

---

## Full Demo Sequence (end to end)

### Sequence A — Supervised loan flow

```
1. Login as PART-008                          POST /auth/login
2. Ask how much you can borrow                POST /chat  "How much can I borrow?"
3. Request a loan                             POST /chat  "I want a $10,000 loan for 5 years"
4. Check what is pending                      GET  /transactions/pending
5. Confirm the loan                           POST /transactions/confirm  → awaiting_bank_details
6. Provide bank details                       POST /transactions/disburse  {routing, account, type}
```

### Sequence B — Human-review hardship flow (full participant → sponsor → participant)

```
1.  Login as PART-008                          POST /auth/login
2.  Submit a hardship for medical              POST /chat  "I need $5,000 for medical expenses"
3.  Upload the medical bill                    POST /documents/upload  (medical_bill.txt)
4.  Re-login as sponsor                        POST /auth/login  (plan_sponsor)
5.  See the pending queue                      GET  /queue  — copy entry_id
6.  Check the documents                        GET  /queue/{entry_id}/docs
7.  Approve the documents                      POST /queue/{entry_id}/approve-docs
8.  Approve the request                        POST /queue/{entry_id}/approve  → approved_awaiting_bank_details
9.  Re-login as participant                    POST /auth/login  (participant)
10. Provide bank details + entry_id            POST /transactions/disburse  {routing, account, type, entry_id}
```

---

## Common Errors

| Error | Reason | Fix |
|---|---|---|
| `401 Unauthorized` | Token expired or not set | Re-login and re-authorize |
| `403 Forbidden` | Wrong role for this endpoint | Switch to the correct role and re-login |
| `400 Documents must be reviewed` | Tried to approve request without approving docs first | Call approve-docs first |
| `404 No pending transaction` | Nothing waiting for confirm/disburse | Check if loan was already executed or cancelled |
| `400 Routing number must be exactly 9 digits` | Invalid routing number format | Provide exactly 9 digits |
| `400 Account number must be between 4 and 17 digits` | Invalid account number | Provide 4–17 digit account number |
| `400 Entry is not awaiting bank details` | Tried to disburse before sponsor approval | Wait for sponsor to approve via POST /queue/{id}/approve first |
| `400 FAP token validation failed: Token has expired` | 24-hour window passed after sponsor approval | Sponsor calls POST /queue/{id}/approve again — re-issues fresh token, no re-review needed |
| `400 Could not extract text` | File is empty or unreadable | Use one of the sample docs in `data/sample_docs/` |
