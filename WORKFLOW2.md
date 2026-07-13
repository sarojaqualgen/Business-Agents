# Aldergate — Path B: LLM + CrewAI Query-Driven Workflow
## Industry-Grade Specification — Agents · Tasks · Tools · Flow

---

## What We Are Building

A **401(k) administration platform** called **Aldergate** — a **TPA (Third-Party Administrator)** built with CrewAI + Claude (LLM) + PLAP/FAP/PAAP (pure-Python compliance engine).

When an employee wants to do something with their retirement account — take a
loan, change contributions, make a withdrawal — strict government regulations
(ERISA laws) must be checked first. Companies currently do this manually or
with outdated software. Aldergate automates the compliance checks, routes
requests to the right people, and maintains the audit trail required by law.

**Active roles (current scope):**
- **Participant (employee)** — self-service: loans, deferrals, distributions, investments
- **Plan Sponsor (HR/employer)** — approves requests, manages plan rules and blackouts, owns the audit log, **and manages all recordkeeper duties** (participant data, account balances, disbursement confirmation)

**Out of scope for current build:**
- **Investment Advisor** — role exists in code but is not active in current flows
- **External Recordkeeper SFTP** (Fidelity/Vanguard/Empower) — Phase 5+, not built; plan sponsor handles all recordkeeper responsibilities until then

---

## Full System — All Layers

```
┌─────────────────────────────────────────────────────────────┐
│  LAYER 1 — Interface (what users see)                        │
│  Currently:  CLI terminal (demo)                            │
│  Phase 4+:   REST API                                       │
│  Phase 7+:   Web portal / mobile app                        │
│  STATUS: ✅ CLI built and demo-ready                         │
└──────────────────────────┬──────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────┐
│  LAYER 2 — LLM Orchestration (natural language → action)     │
│  ← This is Aldergate (TPA) — the core of what we built      │
│                                                             │
│  Employee types: "I want a $10,000 loan over 5 years"       │
│  Claude (LLM) interprets, routes, and responds              │
│                                                             │
│  Intent Agent    → understands what the employee wants      │
│  Data Agent      → fetches plan rules + account data        │
│  Compliance Agent → calls the compliance engine (FAP)       │
│                                                             │
│  Powered by CrewAI + Claude (claude-sonnet-4-6)             │
│  STATUS: ✅ Built — ParticipantCrew, SponsorCrew, AdvisorCrew│
└──────────────────────────┬──────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────┐
│  LAYER 3 — Compliance Engine  (pure Python, no AI)           │
│  ← Also part of Aldergate — PLAP/FAP/PAAP are our code      │
│                                                             │
│  PLAP  "What does this plan allow?"                         │
│        reads plan rules: loan policy, vesting, hardship     │
│                                                             │
│  FAP   "Is this legally allowed?"                           │
│        runs 12 ERISA rules in sequence, fail-fast           │
│        issues signed JWT token if all 12 pass               │
│        writes to audit log on every decision                │
│                                                             │
│  PAAP  "Execute it"                                         │
│        only executes writes when given a valid FAP token    │
│        routes to sponsor queue if autonomy=human_review     │
│                                                             │
│  STATUS: ✅ Built — 87 tests, every rule pass + fail        │
└──────────────────────────┬──────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────┐
│  LAYER 4 — Database                                          │
│  Stores: plans, participants, tokens, audit log, queue      │
│                                                             │
│  PostgreSQL reads + writes fully wired (data/db.py)         │
│  review queue → PostgreSQL (JSON fallback if DB absent)     │
│  REST API wired to compliance engine (Phase 4 complete)     │
│  All PAAP mutations written to DB (Phase 6 complete)        │
│                                                             │
│  STATUS: ✅ Reads + writes fully wired. Redis pending.      │
└──────────────────────────┬──────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────┐
│  LAYER 5 — Recordkeeper                                      │
│  Holds the investment ledger, confirms disbursements         │
│                                                             │
│  Current scope: Plan sponsor manually manages participant    │
│  data, confirms balances, and processes disbursements.       │
│  No external SFTP integration.                              │
│                                                             │
│  Phase 5+ (out of scope now):                               │
│    External SFTP integration with Fidelity/Vanguard/Empower  │
│    Nightly balance file → PostgreSQL participants table      │
│    Outbound instruction file → ACH disbursement             │
│                                                             │
│  STATUS: ⏳ Out of scope — plan sponsor handles this now    │
└─────────────────────────────────────────────────────────────┘
```

---

## One Employee Request — Complete Flow (Hardship Example)

```
Employee types:
"I need a $5,000 hardship withdrawal for a medical emergency"
         │
         ▼
[Layer 2] Intent Agent (LLM)
Understands: action=hardship_distribution, amount=5000, expense=medical
         │
         ▼
[Layer 2] Data Agent (LLM)
Calls PLAP → fetches plan rules: hardship permitted, medical is valid ✓
Calls PAAP → fetches employee account: vested $80k, active, eligible ✓
         │
         ▼
[Layer 2] Compliance Agent (LLM calls FAP)
[Layer 3] FAP runs all 12 ERISA rules in pure Python:
  Rule 1  Delegation Validity      ✓ agent registered
  Rule 2  Blackout Period          ✓ no blackout active
  Rule 3  Participation            ✓ eligibility date passed
  Rule 4  Vesting                  ✓ 7yr service, fully vested
  Rule 5  Contribution Limits      ✓ n/a for distributions
  Rule 6  Plan Rules               ✓ medical is approved expense
  Rule 7  Early Withdrawal         ✓ hardship exception applies
  Rule 8  Anti-Alienation          ✓ not pledging as collateral
  Rule 9  Prohibited Transaction   ✓ no party-in-interest conflict
  Rule 10 Prudent Expert           ✓ no condition added
  Rule 11 RMD Prevention           ✓ rmd_required=false
  Rule 12 Autonomy Level           → human_review (hardship always needs sponsor)

FAP writes decision to audit log (ERISA §107 — 6-year retention)
FAP issues signed JWT token
         │
         ▼
[Layer 2] Data Agent (LLM)
Calls PAAP ExecuteTransaction → autonomy=human_review → goes to queue
Saves to review_queue_state.json (persists to disk)
         │
         ▼
Employee sees:
"Your request is submitted. Reference: AB064BBC.
 A plan administrator will review within 1–3 business days."

── DOCUMENT UPLOAD (participant, immediately after queuing) ──
CLI prompts: "DOCUMENT UPLOAD REQUIRED — Hardship · medical
              Please upload: medical bill, hospital statement, or doctor invoice"
Employee picks [1] Use sample document: Metro General Hospital medical bill
Claude Haiku verifies: ✓ "Medical bill from Metro General Hospital, 2026-05-14, $1,865 due"
Document stored, linked to AB064BBC
         │
         ▼
Employee types "status" → instantly reads from queue file → sees PENDING ⏳
         │
         ▼
[Layer 1] HR Sponsor types: "queue"     (instant, no LLM)
Sees: [AB064BBC]  PART-008  Hardship Distribution  $5,000
      📎 1 doc  (LLM verified · awaiting your review)
         │
         ▼  Step 1 — Read the document
[Layer 1] HR Sponsor types: "docs AB064BBC"
Sees: medical_bill.txt · LLM verified ✓ · "Medical bill from Metro General Hospital, $1,865"
      Status: Awaiting your approval
         │
         ▼  Step 2 — Approve the document
[Layer 1] HR Sponsor types: "approve doc AB064BBC"
Sees: ✓ Document approved  Medical bill / invoice  (medical_bill.txt)
      "Documents approved. You may now approve the request."
         │
         ▼  Step 3 — Approve the request
[Layer 1] HR Sponsor types: "Approve AB064BBC — valid medical docs"
System checks: sponsor_doc_approved=True ✓ — approval allowed
Entry marked approved. Sponsor note saved to queue file.

Note: Sponsor Approve is BLOCKED until sponsor runs "approve doc <entry_id>" first.
         │
         ▼
Employee types "status" → sees APPROVED ✓ + sponsor note
         │
         ▼
[Phase 4 — Built] Sponsor approves via REST API:
POST /queue/AB064BBC/approve  { note: "valid medical docs" }

PAAP executes — transaction recorded:
  · hardship distribution logged: $5,000
  · entry status: approved
  · FAP audit log updated

Done. ~40 seconds from sponsor clicking Approve to transaction recorded.

vested_balance decrement ($80k → $75k) written to PostgreSQL immediately on execution.
```

**What is complete:** Full flow — participant types → FAP 12 rules → document upload → LLM verification → sponsor approves → PAAP executes → vested_balance decremented in PostgreSQL → transaction recorded.
**What is remaining:** Redis (token cache survives restarts), notifications, audit CSV export, UI portals.

---

## Current Build Status

```
✅ Built and complete
   Layer 3: PLAP, FAP (12 rules), PAAP — pure Python, 87 tests
   Layer 2: Intent Agent, Data Agent, Compliance Agent, Participant Agent (CrewAI + Claude)
   Layer 1: CLI — participant + sponsor sessions
            Live streaming display, fast-path commands, role switching
   Layer 1+: FastAPI REST API — all endpoints built (Phase 4 complete)
             SSE streaming, JWT session auth, document upload, queue, admin, disburse
   Layer 4: PostgreSQL — ALL writes wired (Phase 6 complete)
            fap_audit_log, fap_tokens, transactions, review_queue, documents
            vested_balance decremented after every disbursement
            Alembic migrations 001 + 002 applied
   Storage:  MinIO (S3-compatible) — document bytes stored in object storage
   Verification: LLM document verification checks participant name on document

⏳ Not yet built
   Layer 7+: Web portal / mobile app — THREE portals needed (see below)
   Layer 5: External recordkeeper SFTP (Phase 5+, out of scope)
             → Plan sponsor manages participant data manually until then
   Redis:    supervised_pending + disbursement_pending + consumed_tokens
             currently in-memory Python dicts/set — die on server restart
             swap to Redis before production deployment
   Notifications: no alert sent to sponsor when a queue entry is submitted
                  sponsor must poll GET /queue manually
   Audit export: GET /admin/audit returns JSON only
                 DOL needs a downloadable CSV — one endpoint to add
```

---

## Overview

When a user types a plain-English query, CrewAI routes them to the correct
domain crew based on their role (participant, plan sponsor, or investment
advisor). Inside each crew, three workflow agents work in sequence: an Intent
Agent that parses the query, a Data Agent that fetches plan/participant data,
and a Compliance Agent that runs all 12 ERISA rules via FAP.

**The compliance engine (PLAP/FAP/PAAP) does not change.** CrewAI agents are
the orchestration layer sitting on top — they interpret queries and call the
compliance engine as tools. The LLM never makes compliance decisions.

**Three domain crews:**
- **ParticipantCrew** — self-service transactions (loans, deferrals, distributions)
- **SponsorCrew** — plan administration (approve queue, blackouts, audit log)
- **AdvisorCrew** — investment recommendations (reallocation, deferral change)

**Recordkeeper is NOT a crew.** It is a built-in back-office module (Phase 5)
that receives PAAP instructions, maintains the investment ledger, processes ACH
disbursements, and runs nightly settlement to update PostgreSQL vested_balance.
We build this ourselves — no external Fidelity/Vanguard/Empower.

---

## System Architecture

```
┌──────────────────────────────────────────────────────────────────────┐
│  PARTICIPANT INPUT                                                    │
│  "I want to borrow $20,000 from my 401k for 5 years"                 │
└────────────────────────────┬─────────────────────────────────────────┘
                             │
                             ▼
┌──────────────────────────────────────────────────────────────────────┐
│  AGENT 1 — Intent Agent                                              │
│  Task: extract_intent                                                │
│  Tools: none (LLM only)                                             │
│  Output: structured IntentPayload JSON                               │
└────────────────────────────┬─────────────────────────────────────────┘
                             │
                             ▼
┌──────────────────────────────────────────────────────────────────────┐
│  AGENT 2 — Data Agent                                                │
│  Task A: fetch_plan_data       Task B: fetch_participant_data        │
│  Tools: GetPlanRulesTool       Tools: GetParticipantSummaryTool      │
│         GetLoanHeadroomTool             GetLoanStatusTool            │
│  Output: PlanContext JSON               ParticipantContext JSON      │
└────────────────────────────┬─────────────────────────────────────────┘
                             │
                             ▼
┌──────────────────────────────────────────────────────────────────────┐
│  AGENT 3 — Compliance Agent                                          │
│  Task: run_compliance                                                │
│  Tools: RunComplianceCheckTool                                       │
│  Output: FapResult JSON (approved/denied + token + autonomy_level)   │
└────────────────────────────┬─────────────────────────────────────────┘
                             │
              ┌──────────────┴─────────────┐
              ▼                            ▼
       [autonomy = full]        [autonomy = supervised]
       AGENT 2 executes         AGENT 1 shows summary
       immediately              waits for "confirm"
              │                            │
              │              ┌─────────────┘
              │              ▼
              │     [user types confirm]
              │     AGENT 2 executes
              │              │
              └──────┬───────┘
                     ▼
       [autonomy = human_review]
       AGENT 1 submits request
       gives reference number
       no execution happens
                     │
                     ▼
┌──────────────────────────────────────────────────────────────────────┐
│  AGENT 1 — Intent Agent (response mode)                              │
│  Task: format_response                                               │
│  Tools: none (LLM only)                                             │
│  Output: plain-English reply to participant                          │
└──────────────────────────────────────────────────────────────────────┘
```

---

## After the Token — The 3 Autonomy Levels

FAP issues a token when all 12 rules pass. The token says the transaction is
ERISA-legal. But the token also carries an `autonomy_level` that tells PAAP
**how carefully to handle it** before moving any money.

```
FAP runs all 12 rules
         │
         │  all pass
         ▼
    TOKEN ISSUED
    (transaction is ERISA-legal)
         │
         │  token also contains autonomy_level
         │
         ├──────────────────┬───────────────────────┐
         │                  │                       │
         ▼                  ▼                       ▼
       full            supervised            human_review


   ┌───────────┐      ┌───────────┐         ┌───────────┐
   │  EXECUTE  │      │   SHOW    │         │   QUEUE   │
   │   NOW     │      │  SUMMARY  │         │    IT     │
   └─────┬─────┘      └─────┬─────┘         └─────┬─────┘
         │                  │                     │
         │            wait for user               │
         │            to type confirm             │
         │                  │                     │
         │            ┌─────┴──────┐              │
         │            │  EXECUTE   │              │
         │            └─────┬──────┘              │
         │                  │                     │
         ▼                  ▼                     ▼
   "Done. Your         "Your loan           "Submitted.
    deferral is         has been             Ref# HW-0042.
    now 8%."            processed."          Admin will call
                                             you in 2-3 days."
```

### `full` — execute immediately

Safe, small, reversible actions. No confirmation needed. PAAP writes it the
moment the token arrives.

```
Example: participant increases deferral from 6% to 8%

Token issued → PAAP writes new deferral % to DB → done

Participant sees:
  "Done. Your contribution is now 8% ($7,600/year).
   Takes effect next payroll cycle."
```

### `supervised` — confirm, then bank details (if funds move)

Big money or hard-to-reverse actions. The participant must see exactly what
they're agreeing to before anything executes. Token is held until they confirm.

FAP token is issued during the chat and the 24-hour clock starts from that moment.
The participant must confirm and provide bank details within 24 hours of sending the message.

For **disbursement actions** (loan_initiation, hardship_distribution, in_service_distribution),
bank details are collected after confirm — never stored, used once per transaction.

```
Example: participant requests a $20,000 loan

POST /chat → 12 rules pass → autonomy=supervised → supervised_pending stored
             ↓
GET  /transactions/pending → UI shows confirmation panel (amount, term, warning)
             ↓
POST /transactions/confirm
  → if disbursement action: status=awaiting_bank_details
    (FAP token moved from supervised_pending to disbursement_pending)
  → if non-disbursement (deferral to 0%): executes immediately
             ↓
POST /transactions/disburse
  { routing_number, account_number, account_type }   ← no entry_id = supervised flow
  → PAAP executes using stored FAP token
  → returns { status: initiated, disbursement: { account_last4, estimated_arrival } }
  → bank details used once, never stored

POST /transactions/cancel → supervised_pending cleared, nothing executes

Non-disbursement supervised (deferral to 0%):
  POST /confirm → executes immediately, no bank step needed

Participant sees at each step:
  [1] "Your loan of $20,000 has been approved — confirm to proceed."
  [2] "Please enter your bank details to receive the funds."
  [3] "Done. Funds will arrive in 3–5 business days to account ****1234."
```

### `human_review` — sponsor approval, then bank details (if funds move)

Legally required human oversight. PAAP cannot execute these no matter what.
The token goes into a queue. A plan administrator reviews it and approves it.
For disbursement actions, participant provides bank details after sponsor approval.

FAP token is **re-issued at the moment the sponsor approves** — the original token
issued during chat is discarded. The participant has 24 hours from approval to
provide bank details. If they miss it, the sponsor must approve again.

For **hardship_distribution** and **qdro**: the participant must upload supporting
documents BEFORE the sponsor can approve. The Approve command is blocked
until at least one verified document is on file for that queue entry.

```
Example: participant requests a hardship withdrawal

POST /chat → 12 rules pass → autonomy=human_review → queue entry created
  entry status: pending · fap_token stored in queue entry
             ↓
POST /documents/upload → participant uploads medical bill
  Claude Haiku verifies document → verified ✓
             ↓
Sponsor: GET /queue → POST /queue/{id}/approve-docs → POST /queue/{id}/approve
  → for disbursement actions: entry status = approved_awaiting_bank_details
    (NOT "approved" yet — participant must still provide bank details)
  → for non-disbursement (beneficiary, QDRO): entry status = approved
             ↓
POST /transactions/disburse
  { routing_number, account_number, account_type, entry_id: "AB064BBC" }
  → system checks entry.status == approved_awaiting_bank_details
  → PAAP executes using fap_token stored in queue entry
  → entry status: approved (finalized)
  → bank details used once, never stored
  → returns { status: initiated, disbursement: { account_last4, estimated_arrival } }

Participant sees:
  [1] "Submitted for sponsor review. Reference: AB064BBC."
  [2] "Your request has been approved — please provide bank details to receive funds."
  [3] "Done. $5,000 will arrive in 3–5 business days to account ****5678."
```

### Summary table

| Level | When FAP assigns it | What executes | Who triggers |
|---|---|---|---|
| `full` | Safe + reversible (deferral increase, rebalance, address) | PAAP writes immediately | System — automatic |
| `supervised` | Big + irreversible (loan, deferral to 0%) | PAAP writes on confirm | Participant confirms |
| `human_review` | Law requires oversight (hardship, in-service, QDRO, beneficiary) | PAAP writes on approval | Sponsor approves |

**In all 3 cases, execution is immediate in the app.** FAP approves → PAAP writes → balance updated. No external delays. Plan sponsor is the authority — when they approve, it's done.

**Documents for human_review:**
- `hardship_distribution` — participant must upload docs before sponsor can approve
- `qdro` — participant must upload signed court order before sponsor can approve
- All other human_review actions (beneficiary, separation, rmd) — no doc requirement

```
full          = legal + safe + reversible  → just do it
supervised    = legal + big + irreversible → make sure they meant it
human_review  = legal + law requires admin → sponsor must sign off → done
```

### FAP Token Lifetime by Autonomy Level

Every FAP approval issues a signed JWT token (24-hour TTL). The token is single-use —
once consumed by PAAP execution it is dead, even if the 24 hours have not elapsed.
The clock starts at different points depending on autonomy level:

| Level | Token issued when | Clock starts | Consumed when |
|---|---|---|---|
| `full` | During chat (crew run) | Doesn't matter | Within the same crew run, seconds later |
| `supervised` | During chat (crew run) | Participant sends the message | Participant provides bank details (or confirms deferral) |
| `human_review` | **On sponsor approval** | **Sponsor clicks Approve** | Participant provides bank details |

**Key difference for `human_review`:** The original token issued during chat is discarded
when the sponsor approves. A fresh token is re-issued at approval time — so the
participant's 24-hour window starts from when the sponsor approved, not from when
the request was originally submitted. This matters because a hardship can sit in the
queue for days before the sponsor reviews it.

```
human_review token lifecycle:

  POST /chat
    → FAP issues token (24hr TTL, starts now)       ← original token, clock running
    → stored in queue entry (status: pending)

  [hours or days pass — sponsor hasn't reviewed yet]

  Sponsor: POST /queue/{id}/approve
    → approve_awaiting_bank() discards original token
    → re-issues a fresh token (24hr TTL, starts NOW) ← new token, fresh clock
    → stored in queue entry (status: approved_awaiting_bank_details)

  Participant: POST /transactions/disburse
    → PAAP validates and consumes the fresh token
    → entry status → approved (finalized)
    → participant has up to 24hr from approval to do this step

  If participant misses the 24hr window:
    → token expires → disburse returns 400 "Token has expired"
    → sponsor must approve again (which re-issues another fresh token)
```

---

## AGENTS

### Agent 1 — Intent Agent

```python
intent_agent = Agent(
    role="Participant Conversation Specialist",
    goal="""Understand exactly what the participant wants to do with their
            retirement account. Extract a structured intent from natural
            language. Ask one follow-up question if critical information
            is missing. Format the final response in plain English after
            the compliance result arrives.""",
    backstory="""You are the front-line assistant for 401(k) participants.
                 You are friendly, clear, and precise. You never make
                 compliance decisions — that is handled by a separate
                 compliance system. Your job is to understand the human
                 and translate their words into structured requests, then
                 translate the system's result back into human language.""",
    tools=[],                        # no tools — LLM reasoning only
    llm=claude_sonnet,               # claude-sonnet-4-6
    memory=True,                     # remembers conversation turns
    verbose=True,
    allow_delegation=False,
)
```

**Responsible for:**
- Understanding free-form participant queries
- Asking one clarifying question if amount or term is missing
- Formatting final approved/denied responses in plain English
- Explaining denials using the `denial_code` + `erisa_citation` from FAP
- Showing confirmation summaries before supervised transactions execute

**Does NOT do:**
- Call any database or compliance tools
- Decide if a transaction is allowed
- Execute any writes

---

### Agent 2 — Data Agent

```python
data_agent = Agent(
    role="Retirement Account Data Retrieval Specialist",
    goal="""Fetch all plan rules and participant account data needed for
            a compliance check. Return clean, structured context. Never
            return raw PII — only the fields that the compliance engine
            needs to evaluate the request.""",
    backstory="""You are the secure data layer between the participant's
                 question and the compliance engine. You know which plan
                 rules apply to which action, and you know what participant
                 data is needed without exposing sensitive fields like
                 date of birth, marital status, or full account balance.""",
    tools=[
        GetPlanRulesTool,
        GetLoanHeadroomTool,
        GetParticipantSummaryTool,
        GetLoanStatusTool,
        ExecuteTransactionTool,      # only called after FAP token issued
    ],
    llm=claude_sonnet,
    memory=False,                    # stateless — fetches fresh data each time
    verbose=True,
    allow_delegation=False,
)
```

**Responsible for:**
- Fetching plan configuration from PLAP
- Fetching participant account data from PAAP
- Executing approved transactions (only after receiving a valid FAP token)
- Enforcing data exposure rules — never passes DOB, SSN, or full balance to the LLM

**Does NOT do:**
- Make compliance decisions
- Interpret queries
- Execute anything without a FAP token

---

### Agent 3 — Compliance Agent

```python
compliance_agent = Agent(
    role="ERISA Fiduciary Compliance Enforcer",
    goal="""Run every authorization request through the full 12-rule ERISA
            compliance engine. Return the exact result — approved or denied —
            with the denial code, the ERISA citation, and the autonomy level.
            Never skip, reorder, or short-circuit the compliance rules.""",
    backstory="""You are the compliance gate. Nothing executes without passing
                 through you. You call the FAP compliance engine and return
                 its exact result. You do not interpret, soften, or modify
                 the compliance decision. If FAP says denied, you say denied.""",
    tools=[
        RunComplianceCheckTool,
    ],
    llm=claude_sonnet,
    memory=False,                    # stateless — each request is independent
    verbose=True,
    allow_delegation=False,
)
```

**Responsible for:**
- Calling `fap.authorize()` with the full `AuthRequest`
- Returning the `FapResult` exactly as received — no modification
- Ensuring the audit log is written (FAP does this internally)

**Does NOT do:**
- Interpret queries
- Fetch data
- Override or modify compliance decisions
- Execute transactions

---

## TASKS

### Task 1 — `extract_intent`

```python
extract_intent = Task(
    description="""
        Read the participant's message and extract their intent.
        
        Determine:
          - action_type: one of [loan_request, deferral_change,
            hardship_withdrawal, in_service_distribution,
            separation_distribution, rmd, investment_reallocation,
            beneficiary_change, balance_query, eligibility_query]
          - amount: decimal or null
          - repayment_years: int or null (loans only)
          - purpose: string or null (hardship only)
          - new_deferral_pct: decimal or null (deferral changes only)
          - penalty_exception: string or null (early withdrawal only)
        
        If action_type is loan_request and amount is null:
          Ask: "How much would you like to borrow, and over how many years
                (up to 5 years, or 15 for a primary home purchase)?"
          Stop and wait for answer before continuing.
        
        If action_type is hardship_withdrawal and purpose is null:
          Ask: "What is the nature of your hardship?
                (medical, tuition, eviction/foreclosure, funeral, home repair)"
          Stop and wait for answer before continuing.
        
        Return a structured IntentPayload JSON object.
    """,
    expected_output="""
        IntentPayload JSON:
        {
          "action_type": "loan_request",
          "amount": 20000.00,
          "repayment_years": 5,
          "purpose": null,
          "new_deferral_pct": null,
          "penalty_exception": null,
          "needs_clarification": false,
          "clarification_question": null
        }
    """,
    agent=intent_agent,
)
```

---

### Task 2 — `fetch_plan_data`

```python
fetch_plan_data = Task(
    description="""
        Using the action_type from the IntentPayload, fetch the relevant
        plan rules from PLAP for the participant's enrolled plan.
        
        For loan_request:
          Call GetPlanRulesTool and GetLoanHeadroomTool.
          Return: loans_permitted, max_loan_term_general,
                  max_loan_term_primary_residence, origination_fee,
                  maintenance_fee, blackout_active.
        
        For deferral_change:
          Call GetPlanRulesTool.
          Return: min_deferral_pct, max_deferral_pct, blackout_active.
        
        For hardship_withdrawal:
          Call GetPlanRulesTool.
          Return: hardship_permitted, approved_expense_types, blackout_active.
        
        For balance_query or eligibility_query:
          Call GetPlanRulesTool only — no participant data needed.
        
        Never return: vesting_breakpoints raw SQL rows, internal plan IDs,
                      or administrative notes.
    """,
    expected_output="""
        PlanContext JSON:
        {
          "plan_id": "PLAN-003",
          "loans_permitted": true,
          "max_loan_term_general_years": 5,
          "max_loan_term_primary_residence_years": 10,
          "loan_headroom": 42500.00,
          "blackout_active": false
        }
    """,
    agent=data_agent,
    context=[extract_intent],        # runs after Task 1 completes
)
```

---

### Task 3 — `fetch_participant_data`

```python
fetch_participant_data = Task(
    description="""
        Fetch the participant's account data from PAAP.
        Return only the fields the compliance engine needs.
        
        Always return:
          participant_id, plan_id, employment_status,
          years_of_vesting_service, eligibility_date,
          vested_balance, vesting_percentage,
          employee_contributions_ytd, employer_contributions_ytd,
          current_deferral_pct, is_hce,
          age_50_or_older, age_60_to_63,
          rmd_required, outstanding_loans[].
        
        Never return:
          date_of_birth (FAP resolves age internally)
          ssn_hash (not needed after lookup)
          total_balance (only vested_balance exposed)
          marital_status (FAP handles QJSA internally)
          compensation_ytd raw value if participant is HCE
        
        For loan requests: also call GetLoanStatusTool to get
          outstanding_balance and highest_balance_last_12_months
          for all existing loans (needed for the §72(p) cap math).
    """,
    expected_output="""
        ParticipantContext JSON:
        {
          "participant_id": "PART-008",
          "plan_id": "PLAN-003",
          "employment_status": "active",
          "years_of_vesting_service": 5.0,
          "eligibility_date": "2021-02-18",
          "vested_balance": 85000.00,
          "vesting_percentage": 1.0,
          "employee_contributions_ytd": 9200.00,
          "employer_contributions_ytd": 3680.00,
          "current_deferral_pct": 0.06,
          "is_hce": false,
          "age_50_or_older": false,
          "age_60_to_63": false,
          "rmd_required": false,
          "outstanding_loans": []
        }
    """,
    agent=data_agent,
    context=[extract_intent],        # runs after Task 1, parallel with Task 2
)
```

---

### Task 4 — `run_compliance`

```python
run_compliance = Task(
    description="""
        Build an AuthRequest from the IntentPayload, PlanContext, and
        ParticipantContext. Call RunComplianceCheckTool with it.
        
        The AuthRequest must include:
          agent_id, participant_id, plan_id, action_type,
          payload (amount, repayment_years, purpose, etc.),
          request_timestamp.
        
        Return the FapResult exactly as received from FAP.
        Do not modify, soften, or reinterpret the compliance result.
        Do not retry a denied request.
        Do not call this tool more than once per request.
        
        The audit log is written by FAP internally. Do not write it again.
    """,
    expected_output="""
        FapResult JSON:
        {
          "approved": true,
          "denial_code": null,
          "erisa_citation": null,
          "autonomy_level": "supervised",
          "fap_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
          "conditions": [],
          "rule_number_failed": null,
          "audit_id": "AUD-2024-00482"
        }
    """,
    agent=compliance_agent,
    context=[extract_intent, fetch_plan_data, fetch_participant_data],
)
```

---

### Task 5 — `execute_or_queue`

```python
execute_or_queue = Task(
    description="""
        Based on the FapResult autonomy_level:
        
        If autonomy_level == "full":
          Call ExecuteTransactionTool immediately with the fap_token.
          Return the execution receipt.
        
        If autonomy_level == "supervised":
          Do NOT execute yet.
          Return a SupervisedSummary for the Intent Agent to show the participant.
          Wait for participant to confirm (this task does not execute —
          a follow-up task handles the confirmed execution).
        
        If autonomy_level == "human_review":
          Do NOT execute.
          Call QueueForReviewTool to create a pending review record.
          Return a QueueReceipt with reference_number and estimated_review_days.
        
        If approved == false:
          Do NOT execute.
          Return the denial details for the Intent Agent to explain.
    """,
    expected_output="""
        One of:
        
        ExecutionReceipt (full):
        { "executed": true, "transaction_id": "TXN-2024-0391",
          "effective_date": "2024-12-20" }
        
        SupervisedSummary (supervised):
        { "requires_confirmation": true, "monthly_payment": 387.00,
          "term_months": 60, "interest_rate": 0.065,
          "disbursement_days": "3-5" }
        
        QueueReceipt (human_review):
        { "queued": true, "reference_number": "HW-2024-0042",
          "estimated_review_days": 3 }
        
        DenialDetail (denied):
        { "denial_code": "LOAN_CAP_EXCEEDED",
          "erisa_citation": "IRC § 72(p)",
          "rule_number_failed": 6,
          "max_allowed": 40000.00 }
    """,
    agent=data_agent,
    context=[run_compliance, extract_intent],
)
```

---

### Task 6 — `format_response`

```python
format_response = Task(
    description="""
        Read the output of execute_or_queue and write a plain-English
        response for the participant. Tone: helpful, clear, no jargon.
        
        If executed (full autonomy):
          Confirm what was done, give the effective date and transaction ID.
        
        If supervised (needs confirmation):
          Show the summary clearly (amount, monthly payment, term, rate).
          End with: "Type 'confirm' to proceed or 'cancel' to stop."
        
        If human_review queued:
          Explain that it needs review.
          Give the reference number and estimated timeframe.
          Mention any relevant consequences (taxes, penalties) if applicable.
        
        If denied:
          Explain what was denied and why, in plain English.
          Always give the specific reason — never say "your request was denied"
          without explaining why.
          Offer an alternative where one exists
          (e.g. if over cap: "The most you can borrow is $40,000 — would you
           like to request that instead?").
        
        Never mention: rule numbers, internal codes like LOAN_CAP_EXCEEDED,
        token strings, audit IDs, or database field names.
    """,
    expected_output="""
        Plain-English participant response string. Examples:
        
        Approved + supervised:
          "Your loan of $20,000 has been approved.
           · Monthly payment: $387/month for 60 months
           · Interest rate: 6.5% (paid back into your account)
           · Processing: 3–5 business days to your bank on file
           
           Type 'confirm' to proceed or 'cancel' to stop."
        
        Denied:
          "Your request for $50,000 was denied. The IRS limits plan loans
           to 50% of your vested balance — since yours is $80,000, the
           maximum you can borrow is $40,000.
           Would you like to request $40,000 instead?"
    """,
    agent=intent_agent,
    context=[execute_or_queue],
)
```

---

## TOOLS

### `GetPlanRulesTool`

```python
class GetPlanRulesInput(BaseModel):
    plan_id: str

@tool("Get Plan Rules")
def get_plan_rules(plan_id: str) -> dict:
    """
    Fetch plan configuration from PLAP.
    Returns: loan policy, hardship policy, vesting type, blackout status,
             eligibility age, contribution limits, fund lineup.
    Does NOT return: raw vesting breakpoints, internal admin notes.
    """
    plan = plap.get_plan(plan_id)
    return {
        "plan_id": plan.plan_id,
        "loans_permitted": plan.loan_policy.loans_permitted,
        "max_loan_term_general_years": plan.loan_policy.max_repayment_years,
        "max_loan_term_primary_residence_years": plan.loan_policy.max_repayment_years_primary_residence,
        "hardship_permitted": plan.hardship_policy.hardship_permitted,
        "approved_hardship_types": plan.hardship_policy.approved_expense_types,
        "blackout_active": plan.blackout_active,
        "eligibility_age": plan.eligibility_age,
        "vesting_type": plan.vesting_schedule.vesting_type,
    }
```

---

### `GetLoanHeadroomTool`

```python
@tool("Get Loan Headroom")
def get_loan_headroom(participant_id: str, plan_id: str) -> dict:
    """
    Calculate the maximum loan amount this participant can request.
    Applies the IRC § 72(p) cap: lesser of ($50k minus highest
    loan balance in last 12 months) or (50% of vested balance).
    Returns the computed headroom — never the raw balance figures.
    """
    participant = paap.get_participant(participant_id)
    highest_12m = max(
        (loan.highest_balance_last_12_months for loan in participant.outstanding_loans),
        default=Decimal("0")
    )
    cap_50k = Decimal("50000") - highest_12m
    cap_50pct = participant.vested_balance * Decimal("0.5")
    headroom = min(cap_50k, cap_50pct)
    return {
        "loan_headroom": float(max(headroom, Decimal("0"))),
        "existing_loans_count": len(participant.outstanding_loans),
    }
```

---

### `GetParticipantSummaryTool`

```python
@tool("Get Participant Summary")
def get_participant_summary(participant_id: str) -> dict:
    """
    Fetch participant account data needed for a compliance check.
    NEVER returns: date_of_birth, ssn_hash, marital_status, full total_balance.
    Returns: vested_balance, employment_status, years_of_service,
             contributions_ytd, deferral_pct, is_hce, age flags, rmd_required.
    """
    p = paap.get_participant(participant_id)
    return {
        "participant_id": p.participant_id,
        "plan_id": p.plan_id,
        "employment_status": p.employment_status.value,
        "years_of_vesting_service": p.years_of_vesting_service,
        "eligibility_date": str(p.eligibility_date),
        "vested_balance": float(p.vested_balance),
        "vesting_percentage": p.vesting_percentage,
        "employee_contributions_ytd": float(p.employee_contributions_ytd),
        "employer_contributions_ytd": float(p.employer_contributions_ytd),
        "current_deferral_pct": p.current_deferral_pct,
        "is_hce": p.is_hce,
        "age_50_or_older": p.age_50_or_older,
        "age_60_to_63": p.age_60_to_63,
        "rmd_required": p.rmd_required,
        "outstanding_loans": [
            {
                "loan_id": loan.loan_id,
                "outstanding_balance": float(loan.outstanding_balance),
                "highest_balance_last_12_months": float(loan.highest_balance_last_12_months),
                "maturity_date": str(loan.maturity_date),
            }
            for loan in p.outstanding_loans
        ],
    }
```

---

### `RunComplianceCheckTool`

```python
@tool("Run Compliance Check")
def run_compliance_check_tool(auth_request_json: str) -> dict:
    """
    THE COMPLIANCE GATE. Runs all 12 ERISA rules in order.
    Writes to audit log on every call (approved AND denied).
    Returns FapResult with approved/denied, denial_code, erisa_citation,
    autonomy_level, and fap_token (if approved).
    
    This tool must be called for every transaction. Never skip it.
    Never call it more than once per request (audit log would double-write).
    """
    request = AuthRequest.model_validate_json(auth_request_json)
    result = fap.authorize(request)
    return result.model_dump()
```

---

### `ExecuteTransactionTool`

```python
@tool("Execute Transaction")
def execute_transaction_tool(fap_token: str, action_type: str, payload_json: str) -> dict:
    """
    Execute a write against the participant's account.
    Requires a valid, unused FAP token. Fails if token is expired,
    already used, or does not match the action_type.
    
    Writes the transaction record to PostgreSQL.
    Returns a transaction_id and effective_date on success.
    """
    payload = json.loads(payload_json)
    result = paap.execute(fap_token=fap_token, action_type=action_type, payload=payload)
    return {
        "executed": True,
        "transaction_id": result.transaction_id,
        "effective_date": str(result.effective_date),
    }
```

---

### `QueueForReviewTool`

```python
@tool("Queue for Human Review")
def queue_for_review_tool(audit_id: str, participant_id: str, action_type: str) -> dict:
    """
    Creates a pending_review record linked to the FAP audit entry.
    Notifies the plan administrator via configured notification channel.
    Returns a reference number the participant can use to track status.
    
    Used for: hardship, separation_distribution, qdro, beneficiary_change, rmd.
    """
    ref = review_queue.submit(audit_id=audit_id, participant_id=participant_id,
                               action_type=action_type)
    return {
        "queued": True,
        "reference_number": ref.reference_number,
        "estimated_review_days": ref.estimated_review_days,
    }
```

---

## CREW ASSEMBLY

```python
# crew/retirement_crew.py

from crewai import Crew, Process

retirement_crew = Crew(
    agents=[
        intent_agent,
        data_agent,
        compliance_agent,
    ],
    tasks=[
        extract_intent,          # Task 1 — Intent Agent
        fetch_plan_data,         # Task 2 — Data Agent   (after Task 1)
        fetch_participant_data,  # Task 3 — Data Agent   (after Task 1, parallel with Task 2)
        run_compliance,          # Task 4 — Compliance Agent (after Tasks 1, 2, 3)
        execute_or_queue,        # Task 5 — Data Agent   (after Task 4)
        format_response,         # Task 6 — Intent Agent (after Task 5)
    ],
    process=Process.sequential,  # tasks run in order; parallel fetch handled internally
    memory=True,                 # crew-level memory for multi-turn conversations
    verbose=True,
    max_rpm=10,                  # max 10 Claude API calls per minute
    share_crew=False,
)
```

---

## TASK DEPENDENCY MAP

```
extract_intent (Task 1)
       │
       ├──────────────────┐
       ▼                  ▼
fetch_plan_data      fetch_participant_data
   (Task 2)              (Task 3)
       │                  │
       └──────────┬───────┘
                  ▼
          run_compliance (Task 4)
                  │
                  ▼
         execute_or_queue (Task 5)
                  │
                  ▼
          format_response (Task 6)
```

Tasks 2 and 3 both depend on Task 1 but not on each other — they can run in
parallel to reduce latency. Task 4 waits for both. Tasks 5 and 6 are strictly
sequential.

---

## PROCESS TYPES

| Setting | Value | Why |
|---|---|---|
| `Process.sequential` | Tasks run in defined order | Compliance must run after data fetch — order enforced |
| `memory=True` | Crew remembers conversation history | Multi-turn chat: "actually, make that $25,000" works |
| `max_rpm=10` | Rate limit on Claude API calls | Prevents accidental runaway billing |
| `share_crew=False` | Crew instance is per-session | Different participants never share context |

---

## AGENT TOOL ACCESS MATRIX

| Tool | Intent Agent | Data Agent | Compliance Agent |
|---|---|---|---|
| `GetPlanRulesTool` | — | ✓ | — |
| `GetLoanHeadroomTool` | — | ✓ | — |
| `GetParticipantSummaryTool` | — | ✓ | — |
| `GetLoanStatusTool` | — | ✓ | — |
| `RunComplianceCheckTool` | — | — | ✓ |
| `ExecuteTransactionTool` | — | ✓ | — |
| `QueueForReviewTool` | — | ✓ | — |

Intent Agent has zero tools — it only reasons. It never touches data or compliance directly.
Compliance Agent has exactly one tool — it only calls FAP. It never reads data or executes.

---

## ERROR HANDLING

| Scenario | What happens |
|---|---|
| Intent Agent cannot parse query | Asks one clarifying question. If still unclear after 2 attempts, replies "I'm not able to help with that. Contact HR." |
| PLAP returns plan not found | Data Agent returns error; Intent Agent tells participant to contact HR with the plan ID |
| FAP token expired during confirm flow | ExecuteTransactionTool raises TokenExpired; Intent Agent restarts from run_compliance |
| FAP called twice for same request | Second call fails (audit_id already exists); Compliance Agent returns the first result |
| CrewAI max_rpm hit | Request queues; participant sees "Processing, please wait…" |
| Participant types "cancel" during supervised | Session cleared; no tools called; "Your request has been cancelled" returned |

---

## CONVERSATION STATE MACHINE

```
[IDLE]
   │  participant sends message
   ▼
[INTENT_EXTRACTION]          ← Task 1 running
   │  clarification needed?
   ├── YES → [WAITING_CLARIFICATION] ← agent asks question, waits
   │              │  participant answers
   │              └──────────────────► back to [INTENT_EXTRACTION]
   │
   └── NO ──────────────────────────► [DATA_FETCH]  ← Tasks 2+3 running
                                           │
                                           ▼
                                      [COMPLIANCE_CHECK] ← Task 4 running
                                           │  result?
                                           ├── DENIED → [RESPONSE] → [IDLE]
                                           │
                                           ├── APPROVED / full
                                           │       → [EXECUTING] → [RESPONSE] → [IDLE]
                                           │
                                           ├── APPROVED / supervised
                                           │       → [AWAITING_CONFIRM]
                                           │              │  participant confirms
                                           │              │  (disbursement action)
                                           │              └──► [AWAITING_BANK_DETAILS]
                                           │                          │  POST /transactions/disburse
                                           │                          └──► [DISBURSING] → [RESPONSE] → [IDLE]
                                           │              │  participant confirms
                                           │              │  (non-disbursement, e.g. deferral to 0%)
                                           │              └──► [EXECUTING] → [RESPONSE] → [IDLE]
                                           │              │  participant cancels
                                           │              └──► [RESPONSE] → [IDLE]
                                           │
                                           └── APPROVED / human_review
                                                   → [QUEUING] → [AWAITING_DOCUMENTS] → [SPONSOR_REVIEW]
                                                          ↑ participant uploads docs · LLM verifies
                                                            sponsor: approve-docs → approve
                                                          ↓
                                                   (disbursement action)
                                                   → [APPROVED_AWAITING_BANK]
                                                          │  POST /transactions/disburse + entry_id
                                                          └──► [DISBURSING] → [IDLE]
                                                   (non-disbursement, e.g. beneficiary, QDRO)
                                                   → [APPROVED] → [IDLE]
```

---

## FILES TO BUILD

```
crew/
├── retirement_crew.py          ← Crew + Process assembly (this file)
├── agents/
│   ├── intent_agent.py         ← Intent Agent definition + system prompt
│   ├── data_agent.py           ← Data Agent definition
│   └── compliance_agent.py    ← Compliance Agent definition
└── tools/
    ├── plap_tools.py           ← GetPlanRulesTool, GetLoanHeadroomTool
    ├── paap_tools.py           ← GetParticipantSummaryTool, GetLoanStatusTool,
    │                              ExecuteTransactionTool, QueueForReviewTool
    └── fap_tools.py            ← RunComplianceCheckTool

chat/
├── session.py                  ← per-participant conversation state + history
├── router.py                   ← entry point: receives message → runs crew → returns reply
└── confirm_handler.py          ← handles "confirm" / "cancel" during supervised flow

tasks/
├── extract_intent.py           ← Task 1 definition
├── fetch_plan_data.py          ← Task 2 definition
├── fetch_participant_data.py   ← Task 3 definition
├── run_compliance.py           ← Task 4 definition
├── execute_or_queue.py         ← Task 5 definition
└── format_response.py          ← Task 6 definition
```

---

## PRODUCTION DATA SOURCES — Where the Data Actually Comes From

Right now the Data Agent calls mock Python dicts. In production there are two
separate data sources that work completely differently.

---

### Source 1 — Plan Data (what PLAP fetches)

**Lives in: our own PostgreSQL** — the 11 tables already built in Phase 2.

We own this data. An admin fills a form, it writes to our DB, PLAP reads it back.
No external dependency.

```
Admin fills plan onboarding form (Phase 4 dashboard)
       │
       │  POST /admin/plans
       ▼
Our PostgreSQL
  plans
  plan_loan_policy
  plan_vesting_schedules
  plan_vesting_breakpoints
  plan_hardship_policy
  plan_funds
       │
       ▼
GetPlanRulesTool  →  Data Agent  →  FAP
```

**How PLAP reads it (production):**
```python
# data/db.py  (already written in Phase 2)
def get_plan(plan_id: str) -> PlanRecord:
    with engine.connect() as conn:
        row = conn.execute(
            text("SELECT * FROM plans WHERE plan_id = :id"),
            {"id": plan_id}
        ).fetchone()
    return PlanRecord(**row._mapping)
```

---

### Source 2 — Participant Data (what PAAP fetches)

**Source of truth: PostgreSQL participants table**

Participant balances, elections, and loan status live in our PostgreSQL.
In the current build, this data is managed manually by the plan sponsor
(recordkeeper duties). In Phase 5+, an external SFTP integration would
auto-sync this table nightly from Fidelity/Vanguard/Empower.

```
Plan Sponsor manages participant data
  (balances, status, elections — manual in current scope)
                        │
                        │  writes/updates managed by plan sponsor
                        ▼
              Our PostgreSQL
              participants table
              participant_loans
              participant_investment_elections
                        │
                        ▼
      GetParticipantSummaryTool → Data Agent → FAP

Phase 5+ (out of scope):
  External Recordkeeper SFTP nightly file drop
  → parser → upsert → PostgreSQL vested_balance updated automatically
```

**PAAP always reads from our PostgreSQL.** In dev, mock_participants.py provides data.
In production (Phase 6), the same table is updated by the plan sponsor (now) or
by the external recordkeeper SFTP pipeline (Phase 5+).

---

### Where GraphQL Fits

GraphQL works as the **query layer between frontends and our PostgreSQL**.
It is not used for internal PLAP/PAAP tool calls — those use SQLAlchemy directly
because they are internal service calls that need tight control over what fields
are exposed.

GraphQL is used at the **external API boundary**:

```
┌─────────────────────────────────────────────────────────┐
│  FRONTENDS                                               │
│                                                         │
│  Admin Dashboard  ──────────────────────────┐           │
│  (plan onboarding, audit log, blackout mgmt) │           │
│                                             │           │
│  Participant Chat UI  ───────────────────┐  │           │
│  (Path B chatbot frontend)               │  │           │
└──────────────────────────────────────────┼──┼───────────┘
                                           │  │
                                           ▼  ▼
                              ┌─────────────────────────┐
                              │   GraphQL API            │
                              │                         │
                              │  Query examples:        │
                              │  · getParticipant(id)   │
                              │  · getPlan(id)          │
                              │  · getAuditLog(part_id) │
                              │  · getOpenLoans(part_id)│
                              └───────────┬─────────────┘
                                          │
                                          ▼
                              ┌─────────────────────────┐
                              │   Our PostgreSQL         │
                              │                         │
                              │  plans                  │
                              │  participants  (synced) │
                              │  fap_audit_log          │
                              │  fap_tokens             │
                              │  agent_registry         │
                              └─────────────────────────┘
```

**Internal tool calls (PLAP/PAAP → DB) use SQLAlchemy directly** — not GraphQL.
This keeps the compliance path fast, simple, and independent of the API layer.

---

### Full Production Data Flow — One Picture

```
PLAN SPONSOR                       PARTICIPANT
(admin + recordkeeper)             types query in chatbot
       │                                  │
       │ fills plan form /                │
       │ manages participant data         │
       ▼                                  ▼
 POST /admin/plans              Aldergate TPA (CrewAI + Claude)
 POST /admin/blackout           PLAP/FAP/PAAP compliance engine
 Participant data managed       FastAPI REST API (Phase 4 done)
 by sponsor manually now
       │                                  │
       └──────────┬───────────────────────┘
                  ▼
           Our PostgreSQL
         (single source for
          our application)
                  │
       ┌──────────┼──────────────┐
       │          │              │
       ▼          ▼              ▼
  SQLAlchemy   GraphQL       SQLAlchemy
  (PLAP tool)  (frontends)   (PAAP tool)
  ← Aldergate (TPA) — PLAP/FAP/PAAP + CrewAI crews own all of this →
       │                         │
       └─────────┬───────────────┘
                 ▼
           Data Agent   (CrewAI — Aldergate TPA)
                 │
                 ▼
          Compliance Agent (FAP)   (CrewAI — Aldergate TPA)
                 │
                 ▼
           Intent Agent (response)  (CrewAI — Aldergate TPA)
                 │
                 ▼ [disbursement actions]
     Participant provides bank details → POST /transactions/disburse
     PAAP executes → funds initiated (simulated in demo)
     [Phase 5+: external SFTP → ACH → participant's bank (3–5 days)]
```

---

### Dev vs Production — What Changes

| Layer | Dev (now) | Production |
|---|---|---|
| Plan data | `plans.py` → PostgreSQL reads (Phase 2 done) | PostgreSQL via psycopg2 |
| Participant data | `participants.py` → PostgreSQL reads (Phase 2 done) | PostgreSQL via psycopg2 (managed by plan sponsor) |
| FAP token store | Python `set` in memory | Redis (TTL-based, survives restarts) |
| External API | FastAPI (Phase 4 done) | Same FastAPI + web portal on top |
| Participant sync | Plan sponsor manages manually | Phase 5+: external SFTP/API pipeline (recordkeeper → Aldergate) |

The PLAP, FAP, and PAAP code does not change between dev and production.
Only the data source behind `get_plan()` and `get_participant()` changes —
from a dict lookup to a PostgreSQL query. Everything else is identical.

---

## PORTALS — Who Needs a UI and What They Can Do

The answer comes directly from the `PrincipalType` enum in `agents/fap/models.py`
and the allowed actions in `data/agents.py`. Every user type that exists in
the system needs a portal. There are 5 principal types — they map to 3 portals
plus one delegated access mode.

---

### The 5 Principal Types (from the code)

```python
class PrincipalType(str, Enum):
    participant            # the employee with the 401k
    plan_sponsor           # the employer / HR team
    investment_advisor     # registered investment advisor (RIA)
    plan_trustee           # the trustee (bank or trust company holding assets)
    participant_delegate   # someone acting FOR a participant (power of attorney,
                           # or QDRO alternate payee receiving funds)
```

---

### Portal 1 — Participant Self-Service Portal

**Who:** The employee. The person whose 401(k) it is.

**Principal type:** `participant` and `participant_delegate`

**What they can do** (from `AGENT-PARTICIPANT-001` allowed_actions = all ActionTypes):

```
Read (no FAP needed):
  · View vested balance and total balance
  · View loan headroom (how much they can borrow)
  · View current deferral %
  · View investment elections
  · View outstanding loans and repayment schedule
  · View transaction history
  · Track status of pending human_review requests (ref number lookup)

Write (every write goes through FAP):
  · Change deferral % (increase or decrease)
  · Change investment elections (rebalance)
  · Request a loan
  · Request hardship withdrawal
  · Request in-service distribution (if age 59½)
  · Request separation distribution (if terminated)
  · Update beneficiary
```

**Delegate sub-mode** (`participant_delegate`):
A participant can grant another person limited access — for example, a spouse
with power of attorney, or an alternate payee receiving funds under a QDRO.
They log into the same portal with their own credentials but only see the
participant's account they are delegated to. FAP checks `principal_type =
participant_delegate` and limits scope accordingly.

---

### Portal 2 — Plan Admin Portal

**Who:** The employer's HR or benefits team, and the plan trustee.

**Principal types:** `plan_sponsor` + `plan_trustee`

**What plan_sponsor can do** (from `AGENT-SPONSOR-001`):

```
Plan management (PLAP writes — no FAP token needed, admin-gated):
  · Onboard a new plan (fill the multi-step plan form)
  · Edit plan settings (vesting, loan policy, hardship criteria)
  · Activate / deactivate a blackout period
    (ERISA § 101(i) — 30-day advance notice to participants required)
  · Add or remove funds from the plan lineup
  · Issue or revoke agents (agent_registry)

Human review queue (the most important admin job):
  · See all requests queued for human_review
  · Review hardship withdrawal requests
  · Review separation distribution requests
  · Process QDRO orders (requires all QDRO fields verified)
  · Approve or reject RMD requests
  · Approve or reject beneficiary changes
  → Each approval calls ExecuteTransactionTool with the FAP token
  → Each rejection writes a denial record to fap_audit_log

Audit and compliance:
  · Full audit log — every FAP decision, approved + denied
  · Filter by participant, date, action type, denial code
  · Export for DOL audit (6-year ERISA § 107 retention)
  · View 402(f) rollover notice history (required before separation)

Participant management (read-only):
  · Search participants by name or ID
  · View a participant's summary (no SSN, no DOB)
  · See a participant's pending requests
```

**What plan_trustee adds:**
The trustee is typically a bank or trust company that legally holds the assets.
They get elevated read access to plan-level data and can sign off on QDROs and
large distributions. In practice, trustee and sponsor functions are often in
the same admin portal — just with different permission levels.

---

### Portal 3 — Advisor Portal

**Who:** A registered investment advisor (RIA) who advises participants on
their investments. Subject to PTE 2020-02 (the DOL exemption for advisors
recommending rollovers or reallocations — enforced in Rule 9).

**Principal type:** `investment_advisor`

**What they can do** (from `AGENT-ADVISOR-001` allowed_actions):

```
Read (their assigned participants only):
  · View participant investment elections
  · View plan fund lineup and performance data
  · View deferral % for participants in their book

Write (through FAP, limited scope):
  · Submit investment reallocation recommendations
    → goes through FAP Rule 9 (PTE 2020-02 check)
    → autonomy = human_review (admin confirms before execution)
  · Submit deferral change recommendations
    → participant must separately confirm (supervised)

Compliance:
  · View their own transaction history (their recommendations only)
  · PTE 2020-02 disclosure management
    (advisors must disclose conflicts before recommending rollovers)
```

**What advisors CANNOT do:**
- Initiate loans, hardship, or distributions — those are participant-only actions
- See balances of participants not assigned to them
- Execute anything without FAP approval

---

### Portal Summary

```
┌───────────────────────────────────────────────────────────────────┐
│  PORTAL 1 — Participant Self-Service                               │
│  Principal: participant, participant_delegate                      │
│                                                                   │
│  · View balance, loan headroom, elections                         │
│  · Request loan / hardship / deferral change / distribution       │
│  · Track pending requests                                         │
│  · Path B: this is the chatbot UI                                 │
│  · Path A: this is a web form dashboard                           │
└───────────────────────────────────────────────────────────────────┘

┌───────────────────────────────────────────────────────────────────┐
│  PORTAL 2 — Plan Admin                                            │
│  Principal: plan_sponsor, plan_trustee                            │
│                                                                   │
│  · Onboard and configure plans                                    │
│  · Manage blackout periods (30-day notice rule)                   │
│  · Approve / reject human_review queue                            │
│  · Full audit log + DOL export                                    │
│  · Manage agent registry                                          │
└───────────────────────────────────────────────────────────────────┘

┌───────────────────────────────────────────────────────────────────┐
│  PORTAL 3 — Advisor                                               │
│  Principal: investment_advisor                                    │
│                                                                   │
│  · View assigned participants (limited fields)                    │
│  · Submit reallocation + deferral recommendations                 │
│  · PTE 2020-02 disclosures                                        │
└───────────────────────────────────────────────────────────────────┘
```

---

### What Is NOT a Portal (automated or out of scope)

```
External Recordkeeper  ← Phase 5+ (Fidelity / Vanguard / Empower)
                         No portal, no crew — automated SFTP pipeline when built
                         Until then: plan sponsor handles recordkeeper duties manually

FAP token store        ← Redis in production, no UI
                         tokens expire in 5 minutes, self-cleaning

Audit log              ← PostgreSQL append-only table
                         admin reads it through Portal 2
                         DOL auditor gets a file export, not a login

Investment Advisor     ← Exists in codebase (AdvisorCrew, AGENT-ADVISOR-001)
                         Out of scope for current build
                         Will be activated when advisor portal is needed
```

---

### Which Portal Uses Which Agent Type

```
Participant Portal  ──► principal_type = participant
                        agent_id = AGENT-PARTICIPANT-{user_id}
                        can request all 9 action types

Advisor Portal     ──► principal_type = investment_advisor
                        agent_id = AGENT-ADVISOR-{advisor_id}
                        limited to: investment_reallocation, deferral_change

Plan Admin Portal  ──► principal_type = plan_sponsor
                        agent_id = AGENT-SPONSOR-{plan_id}
                        allowed_plan_ids = ["*"]  (all plans)
                        limited to: beneficiary_update, qdro, rmd
                        (admin also has non-FAP powers: plan config, blackout)
```

Every portal action that touches a participant account goes through FAP.
Plan configuration (onboarding, blackout toggle) is admin-only and bypasses FAP
because it modifies plan rules, not participant accounts.

---

## FULL ORCHESTRATION TREE — Complete Picture

This is the complete picture for one user query from start to finish.
Shows every agent call, every tool call, every task, and every output.

---

### How Agents Work in CrewAI (Important to Understand First)

Agents are defined once and reused across multiple tasks.
They are NOT created fresh for each task — the same agent object handles multiple tasks.
CrewAI passes the output of each task as context into the next one.

```
3 agents defined → 6 tasks assigned → tasks run in order → agents reused

Intent Agent     → used in Task 1  and  Task 6   (called TWICE)
Data Agent       → used in Task 2, Task 3, Task 5 (called THREE TIMES)
Compliance Agent → used in Task 4                 (called ONCE)
```

---

### Full Orchestration Tree

```
┌──────────────────────────────────────────────────────────────────────┐
│  PLAN SPONSOR (admin + recordkeeper)                                  │
│  Manages participant data, approves queue, handles disbursements     │
│                                                                      │
│  Current scope — plan sponsor is the recordkeeper:                   │
│    Manages vested_balance, employment status, elections manually     │
│    After approving disbursement: participant provides bank details   │
│    via POST /transactions/disburse → funds initiated (simulated)    │
│                                                                      │
│  Phase 5+ (out of scope):                                            │
│    External SFTP integration with Fidelity/Vanguard/Empower         │
│    Nightly inbound file → PostgreSQL vested_balance updated          │
│    Outbound instruction file → ACH to participant's bank (3–5 days) │
└──────────────────────────────┬───────────────────────────────────────┘
                               │ participants table (mocks in dev, PostgreSQL reads wired)
                               ▼
              ┌────────────────────────────────────────┐
              │  PostgreSQL                             │
              │  plans · participants · audit_log · tokens│
              └────────────────┬───────────────────────┘
                               │ Data Agent reads at query time (Tasks 2 + 3)
                               ▼

USER QUERY
"I want to borrow $20,000 from my 401k for 5 years"
│
▼
RETIREMENT CREW starts  ← Aldergate (TPA: CrewAI + Claude + PLAP/FAP/PAAP)
├── Agents loaded: Intent Agent, Data Agent, Compliance Agent
├── Tasks queued: 6 tasks in sequence
└── Process: Sequential (Tasks 2+3 run in parallel internally)
│
│
├─────────────────────────────────────────────────────────────────
│  TASK 1 — extract_intent
│  Agent  : Intent Agent  ← 1st use of this agent
│  Tools  : none (pure LLM reasoning)
│  Input  : raw user query string
│  Work   : reads sentence → identifies action=loan_request,
│           amount=20000, repayment_years=5, no clarification needed
│  Output : IntentPayload JSON
│           {
│             "action_type": "loan_request",
│             "amount": 20000.00,
│             "repayment_years": 5,
│             "needs_clarification": false
│           }
│
│  [if needs_clarification = true]
│  Intent Agent asks: "How much and for how many years?"
│  Waits for reply → loops back → re-runs Task 1 with new input
│─────────────────────────────────────────────────────────────────
│
│  IntentPayload passed to Tasks 2 and 3 as context
│
│         ┌───────────────────────────┐
│         │  Tasks 2 + 3 run in       │
│         │  parallel — both need     │
│         │  Task 1 output but not    │
│         │  each other               │
│         └───────────────────────────┘
│
├─────────────────────────────────────────────────────────────────
│  TASK 2 — fetch_plan_data                TASK 3 — fetch_participant_data
│  Agent  : Data Agent (2nd use)           Agent  : Data Agent (3rd use)
│  Tools  :                                Tools  :
│   ├── GetPlanRulesTool                    ├── GetParticipantSummaryTool
│   │    calls plap.get_plan()              │    calls paap.get_participant()
│   │    reads from PostgreSQL              │    reads from PostgreSQL
│   │    returns loan policy,              │    returns vested_balance,
│   │    vesting type, blackout,           │    employment_status,
│   │    eligible expense types            │    years_of_service,
│   │                                      │    contributions_ytd,
│   └── GetLoanHeadroomTool                │    deferral_pct, is_hce,
│        computes IRC §72(p) cap           │    age flags, rmd_required
│        $50k − highest_12m               │
│        vs 50% × vested_balance          └── GetLoanStatusTool
│        returns: loan_headroom=40000          reads outstanding_loans[]
│                                              returns principal,
│  Output: PlanContext JSON                    outstanding_balance,
│  {                                           highest_balance_last_12m
│    "loans_permitted": true,
│    "max_loan_term_general_years": 5,         Output: ParticipantContext JSON
│    "loan_headroom": 40000.00,                {
│    "blackout_active": false                    "vested_balance": 80000.00,
│  }                                             "employment_status": "active",
│                                               "years_of_vesting_service": 7.0,
│                                               "vesting_percentage": 1.0,
│                                               "outstanding_loans": []
│                                             }
│─────────────────────────────────────────────────────────────────
│
│  Both outputs passed to Task 4 as context (along with Task 1 output)
│
├─────────────────────────────────────────────────────────────────
│  TASK 4 — run_compliance
│  Agent  : Compliance Agent  ← only use of this agent
│  Tools  :
│   └── RunComplianceCheckTool
│        builds AuthRequest from Tasks 1+2+3 outputs
│        calls fap.authorize(auth_request)
│        │
│        │  FAP runs all 12 rules in order — stops at first failure
│        │
│        ├── Rule 1  delegation_validity     ✓ agent registered + in scope
│        ├── Rule 2  blackout_period         ✓ no active blackout
│        ├── Rule 3  eligibility             ✓ eligibility_date passed
│        ├── Rule 4  vesting                 ✓ 7yr service, fully vested
│        ├── Rule 5  contribution_limits     ✓ not a deferral change, skip
│        ├── Rule 6  plan_rules (loan cap)   ✓ $20k < $40k headroom
│        ├── Rule 7  early_withdrawal        ✓ age 46, no pre-59½ issue
│        ├── Rule 8  anti_alienation         ✓ not pledging as collateral
│        ├── Rule 9  prohibited_transaction  ✓ no party-in-interest
│        ├── Rule 10 prudent_expert          ✓ adds no condition (low stakes)
│        ├── Rule 11 rmd_prevention          ✓ rmd_required=false
│        └── Rule 12 autonomy_level          → supervised (loan initiation)
│        │
│        │  FAP writes to fap_audit_log in PostgreSQL  ← always, pass or fail
│        │  FAP issues JWT token  ← only because all 12 passed
│        │
│  Output: FapResult JSON
│  {
│    "approved": true,
│    "denial_code": null,
│    "autonomy_level": "supervised",
│    "fap_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
│    "audit_id": "AUD-2024-00482"
│  }
│─────────────────────────────────────────────────────────────────
│
│  FapResult passed to Task 5 as context
│
├─────────────────────────────────────────────────────────────────
│  TASK 5 — execute_or_queue
│  Agent  : Data Agent  ← 4th use of this agent
│
│  Reads autonomy_level from FapResult → branches:
│
│  ┌──────────────────────────────────────────────────────────┐
│  │ autonomy = full                                          │
│  │ Tools: ExecuteTransactionTool (called immediately)       │
│  │        passes fap_token to PAAP                          │
│  │        PAAP validates token → writes to PostgreSQL       │
│  │ Output: ExecutionReceipt                                 │
│  │         { "executed": true, "transaction_id": "TXN-..." }│
│  └──────────────────────────────────────────────────────────┘
│
│  ┌──────────────────────────────────────────────────────────┐
│  │ autonomy = supervised  (this example)                    │
│  │ Tools: none yet                                          │
│  │ Output: SupervisedSummary                                │
│  │         { "monthly_payment": 387.00, "term_months": 60, │
│  │           "interest_rate": 0.065 }                       │
│  │                                                          │
│  │ → Task 6 shows summary to participant                    │
│  │ → participant confirms: POST /transactions/confirm       │
│  │   (loan is disbursement → awaiting_bank_details)        │
│  │ → participant enters bank details:                       │
│  │   POST /transactions/disburse                           │
│  │   { routing_number, account_number, account_type }      │
│  │ → PAAP validates FAP token → transaction recorded        │
│  │   (vested_balance updated in PostgreSQL)                       │
│  └──────────────────────────────────────────────────────────┘
│
│  ┌──────────────────────────────────────────────────────────┐
│  │ autonomy = human_review                                  │
│  │ Tools: QueueForReviewTool                                │
│  │        creates pending_review record in queue file       │
│  │ Output: QueueReceipt { "reference_number": "HW-0042" }  │
│  │ PAAP does NOT execute — sponsor must approve first       │
│  │                                                          │
│  │ → participant uploads docs (hardship/QDRO required)      │
│  │ → sponsor: approve-docs → approve                        │
│  │   POST /queue/{id}/approve                               │
│  │   (disbursement actions → approved_awaiting_bank_details)│
│  │ → participant enters bank details:                       │
│  │   POST /transactions/disburse                           │
│  │   { routing_number, account_number, account_type,       │
│  │     entry_id }                                           │
│  │ → PAAP validates FAP token → transaction recorded        │
│  │   (vested_balance updated in PostgreSQL)                       │
│  └──────────────────────────────────────────────────────────┘
│
│  ┌──────────────────────────────────────────────────────────┐
│  │ approved = false (FAP denied)                            │
│  │ Tools: none                                              │
│  │ Output: DenialDetail                                     │
│  │         { "denial_code": "LOAN_CAP_EXCEEDED",            │
│  │           "erisa_citation": "IRC § 72(p)",               │
│  │           "max_allowed": 40000.00 }                      │
│  │ Nothing executes. Audit log already written by FAP.      │
│  └──────────────────────────────────────────────────────────┘
│─────────────────────────────────────────────────────────────────
│
│  Task 5 output passed to Task 6 as context
│
└─────────────────────────────────────────────────────────────────
   TASK 6 — format_response
   Agent  : Intent Agent  ← 2nd use of this agent
   Tools  : none (pure LLM reasoning)
   Input  : output from Task 5
   Work   : reads SupervisedSummary → writes plain-English reply
   Output : string sent back to participant

   "Your loan of $20,000 has been approved.
    · Monthly payment: $387/month for 60 months
    · Interest rate: 6.5% (paid back into your account)

    Type 'confirm' to proceed or 'cancel' to stop."
─────────────────────────────────────────────────────────────────

── EXECUTION PATHS (after Task 6 response) ──────────────────────

Does this action move money out of the account?
         │
         ├── NO — deferral_change · investment_reallocation
         │         address_update · beneficiary_update · qdro
         │         │
         │         ▼
         │  ┌──────────────────────────────────────────────────┐
         │  │  PAAP EXECUTES IMMEDIATELY                        │
         │  │  FAP token validated → transaction recorded       │
         │  │  ~40 seconds from confirm / sponsor approve       │
         │  │  no balance change — record update only           │
         │  └──────────────────────────────────────────────────┘
         │
         └── YES — loan_initiation
                   hardship_distribution
                   in_service_distribution
                        │
                        ├── autonomy = supervised (loan_initiation)
                        │        │
                        │        ▼
                        │  ┌───────────────────────────────────┐
                        │  │  STEP 1 — PARTICIPANT CONFIRMS    │
                        │  │  POST /transactions/confirm        │
                        │  │  → { status: awaiting_bank_details}│
                        │  └───────────────────────────────────┘
                        │        │
                        │        ▼
                        │  ┌───────────────────────────────────┐
                        │  │  STEP 2 — BANK DETAILS            │
                        │  │  POST /transactions/disburse       │
                        │  │  {                                 │
                        │  │    routing_number: "021000021",    │
                        │  │    account_number: "xxxxxxxx",     │
                        │  │    account_type:   "checking"      │
                        │  │  }                                 │
                        │  │  used once · never stored          │
                        │  └───────────────────────────────────┘
                        │        │
                        │        ▼
                        │  ┌───────────────────────────────────┐
                        │  │  PAAP EXECUTES                    │
                        │  │  transaction recorded     │
                        │  │  vested_balance decremented in PostgreSQL│
                        │  └───────────────────────────────────┘
                        │
                        └── autonomy = human_review
                            (hardship_distribution, in_service_distribution)
                                 │
                                 ▼
                           ┌───────────────────────────────────┐
                           │  STEP 1 — PARTICIPANT UPLOADS DOCS│
                           │  POST /documents/upload            │
                           │  Claude Haiku verifies             │
                           │  (required before sponsor approves │
                           │   for hardship + qdro)             │
                           └───────────────────────────────────┘
                                 │
                                 ▼
                           ┌───────────────────────────────────┐
                           │  STEP 2 — SPONSOR APPROVES        │
                           │  GET  /queue/{id}/docs             │
                           │  POST /queue/{id}/approve-docs     │
                           │  POST /queue/{id}/approve          │
                           │  → { status:                       │
                           │      approved_awaiting_bank_details}│
                           └───────────────────────────────────┘
                                 │
                                 ▼
                           ┌───────────────────────────────────┐
                           │  STEP 3 — BANK DETAILS            │
                           │  POST /transactions/disburse       │
                           │  {                                 │
                           │    routing_number: "021000021",    │
                           │    account_number: "xxxxxxxx",     │
                           │    account_type:   "checking",     │
                           │    entry_id:       "AB064BBC"      │
                           │  }                                 │
                           │  used once · never stored          │
                           └───────────────────────────────────┘
                                 │
                                 ▼
                           ┌───────────────────────────────────┐
                           │  PAAP EXECUTES                    │
                           │  transaction recorded     │
                           │  vested_balance decremented in PostgreSQL│
                           └───────────────────────────────────┘
─────────────────────────────────────────────────────────────────
```

## After the Token — The 3 Autonomy Levels

FAP issues a token when all 12 rules pass. The token says the transaction is
ERISA-legal. But the token also carries an `autonomy_level` that tells PAAP
**how carefully to handle it** before moving any money.

```
FAP runs all 12 rules
         │
         │  all pass
         ▼
    TOKEN ISSUED
    (transaction is ERISA-legal)
         │
         │  token also contains autonomy_level
         │
         ├──────────────────┬───────────────────────┐
         │                  │                       │
         ▼                  ▼                       ▼
       full            supervised            human_review


   ┌───────────┐      ┌───────────┐         ┌───────────┐
   │  EXECUTE  │      │   SHOW    │         │   QUEUE   │
   │   NOW     │      │  SUMMARY  │         │    IT     │
   └─────┬─────┘      └─────┬─────┘         └─────┬─────┘
         │                  │                     │
         │            wait for user               │
         │            to type confirm             │
         │                  │                     │
         │            ┌─────┴──────┐              │
         │            │  EXECUTE   │              │
         │            └─────┬──────┘              │
         │                  │                     │
         ▼                  ▼                     ▼
   "Done. Your         "Your loan           "Submitted.
    deferral is         has been             Ref# HW-0042.
    now 8%."            processed."          Admin will call
                                             you in 2-3 days."
```

### `full` — execute immediately

Safe, small, reversible actions. No confirmation needed. PAAP writes it the
moment the token arrives.

```
Example: participant increases deferral from 6% to 8%

Token issued → PAAP writes new deferral % to DB → done

Participant sees:
  "Done. Your contribution is now 8% ($7,600/year).
   Takes effect next payroll cycle."
```

### `supervised` — show summary, wait for confirm, then execute

Big money or hard-to-reverse actions. Token is held until the participant confirms.
On confirm, PAAP executes immediately — vested_balance updated in the app at once.

```
Example: participant requests a $20,000 loan

Token issued → Intent Agent shows summary → participant confirms
             → POST /transactions/confirm
             → PAAP executes immediately
             → loan recorded, vested_balance reduced by $20,000

             Cancel → token discarded, nothing changes

Participant sees:
  [1] "Your loan of $20,000 has been approved — confirm to proceed."
  [2] "Done. Loan of $20,000 processed. Your vested balance has been updated."
```

### `human_review` — sponsor approval → PAAP executes immediately

Legally required human oversight. PAAP cannot execute without the sponsor.
The token goes into a queue. The plan sponsor reviews, approves, and PAAP
executes immediately — vested_balance updated in ~40 seconds, no external transfer.

```
Example: participant requests a hardship withdrawal

Token issued → request queued → participant uploads docs → LLM verifies
             → sponsor: approve-docs → approve
             → POST /queue/{id}/approve
             → PAAP executes → transaction recorded

Done in ~40 seconds. No external delays. Plan sponsor approved it — it's done.
(vested_balance decremented in PostgreSQL on every disbursement.)

(non-disbursement, e.g. QDRO, beneficiary) → same: approved immediately

Participant sees:
  [1] "Submitted for review. Reference: AB064BBC."
  [2] (after sponsor approves) "Your request has been approved.
       $5,000 has been removed from your vested balance."
```

---

### Agent Reuse Summary

```
┌────────────────────┬──────────────────────────────────────┬───────────┐
│ Agent              │ Tasks it handles                     │ Used how  │
├────────────────────┼──────────────────────────────────────┼───────────┤
│ Intent Agent       │ Task 1 (extract_intent)              │           │
│                    │ Task 6 (format_response)             │  2 times  │
├────────────────────┼──────────────────────────────────────┼───────────┤
│ Data Agent         │ Task 2 (fetch_plan_data)             │           │
│                    │ Task 3 (fetch_participant_data)       │  3 times  │
│                    │ Task 5 (execute_or_queue)            │           │
├────────────────────┼──────────────────────────────────────┼───────────┤
│ Compliance Agent   │ Task 4 (run_compliance)              │  1 time   │
└────────────────────┴──────────────────────────────────────┴───────────┘

Same agent object — not recreated. CrewAI passes task context between uses.
```

---

### Tool Call Count Per Query

```
┌──────────────────────────────┬──────────┬────────────────────────────┐
│ Tool                         │ Calls    │ When                       │
├──────────────────────────────┼──────────┼────────────────────────────┤
│ GetPlanRulesTool             │ 1        │ Task 2 always              │
│ GetLoanHeadroomTool          │ 0 or 1   │ Task 2, loan requests only │
│ GetParticipantSummaryTool    │ 1        │ Task 3 always              │
│ GetLoanStatusTool            │ 0 or 1   │ Task 3, loan requests only │
│ RunComplianceCheckTool       │ 1        │ Task 4 always, exactly once│
│ ExecuteTransactionTool       │ 0 or 1   │ Task 5, if approved        │
│ QueueForReviewTool           │ 0 or 1   │ Task 5, human_review only  │
├──────────────────────────────┼──────────┼────────────────────────────┤
│ Total (loan request)         │ 5–6      │                            │
│ Total (balance query)        │ 2        │ no FAP needed, read only   │
│ Total (deferral change)      │ 3–4      │ no loan tools needed       │
└──────────────────────────────┴──────────┴────────────────────────────┘
```

---

### What Persists After Every Query

```
PostgreSQL writes after one approved loan request:
  fap_audit_log     ← 1 row written by FAP (always, even if denied)
  fap_tokens        ← 1 row written (consumed when PAAP executes)
  participant_loans ← 1 row written by PAAP (only on execute)

Redis writes (production):
  fap_tokens        ← token with 5-minute TTL (replaces DB token store)

Nothing else is written. Plan data is never mutated by a participant query.
```

---

## WHAT NEVER CHANGES

No matter how the interface evolves, these invariants are permanent:

```
1. All 12 FAP rules run on every write. No exceptions.
2. PAAP never executes without a valid FAP token.
3. FAP audit log is written on every decision — approved AND denied.
4. Date of birth, SSN, marital status never passed to the LLM.
5. Full account balance never passed to the LLM — only loan_headroom or rmd_amount.
6. Compliance decisions are pure Python. LLM never approves or denies.
```

---

## DOMAIN CREW ARCHITECTURE (Phase 3 — Built)

### Two Layers

```
┌─────────────────────────────────────────────────────────────────────┐
│  LAYER 1 — DOMAIN CREWS  (who is logged in determines which crew)   │
│                                                                     │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐  │
│  │  ParticipantCrew │  │   SponsorCrew    │  │   AdvisorCrew    │  │
│  │  (self-service)  │  │ (plan admin)     │  │ (investment recs)│  │
│  └────────┬─────────┘  └────────┬─────────┘  └────────┬─────────┘  │
│           │                     │                     │             │
│  ┌────────▼──────────────────────▼──────────────────────▼────────┐  │
│  │  LAYER 2 — WORKFLOW AGENTS  (inside each crew)                │  │
│  │                                                               │  │
│  │  Intent Agent   Data Agent   Compliance Agent                 │  │
│  │  (no tools)     (PLAP/PAAP)  (FAP only)                      │  │
│  └───────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
```

### Domain Crew Scope

| Crew | Entry File | Agents | Tasks | Key Tools |
|---|---|---|---|---|
| ParticipantCrew | crew/crews/participant_crew.py | 3 | 6 | GetPlanRules, GetParticipantSummary, GetLoanHeadroom, RunComplianceCheck, ExecuteTransaction |
| SponsorCrew | crew/crews/sponsor_crew.py | 3 | 4 | GetPendingReviews, ApproveRequest, DenyRequest, ManageBlackout, GetAuditLog |
| AdvisorCrew | crew/crews/advisor_crew.py | 3 | 5 | GetFundLineup, GetParticipantSummary, RunComplianceCheck, ExecuteTransaction |
| Router | crew/router.py | — | — | Routes by principal_type string |

### Recordkeeper Role (Current Scope)

In the current build, there is **no external recordkeeper** (Fidelity, Vanguard, Empower).
The **plan sponsor handles all recordkeeper duties**:

- Managing participant account data (balances, elections, loan status)
- Confirming disbursements after approving human_review requests
- Participant data sync and account management (done manually by sponsor)

There is no RecordkeeperCrew. External SFTP integration is Phase 5+ and out of scope.
The two active crews are:

```
ParticipantCrew — handles all self-service participant transactions
SponsorCrew — handles plan admin AND recordkeeper duties (approvals, queue, data)
```

AdvisorCrew exists in the codebase but is out of scope for the current build.

### Plan Sponsor Full Duties (admin + recordkeeper)

The plan sponsor is the single admin authority. They handle both plan administration and all recordkeeper responsibilities in the current scope.

```
Plan Administration (SponsorCrew):
  1. Approve/deny human_review queue
     - hardship distributions (ERISA § 401(k)(2)(B))
     - QDROs (ERISA § 206(d) — within 18-month determination window)
     - RMD scheduling (IRC § 401(a)(9))
     - beneficiary updates
     - separation distributions with rollover notices

  2. Manage blackout periods
     - activate / deactivate
     - ERISA § 101(i): mandatory 30-day advance participant notice

  3. View FAP audit log
     - ERISA § 107: 6-year minimum retention
     - DOL subpoena target — must be complete and accurate

  4. Nondiscrimination testing oversight
     - ADP/ACP testing (IRC § 401(k)(3) / § 401(m)(2))
     - Top-heavy testing (IRC § 416)
     - Results trigger corrective distributions if failed

  5. Forfeiture management
     - Non-vested employer match when participant terminates
     - Allocate forfeitures each plan year

  6. Mass notices (annual / event-driven)
     - Safe harbor notice (before plan year)
     - 402(f) rollover notice (before separation distributions)
     - Summary Annual Report (SAR)
     - Blackout notice (30 days before)

  7. Plan amendments
     - Update loan policy, vesting schedule, fund lineup
     - Material amendments require participant notice (ERISA § 204(h))

  8. Agent registry management
     - Add/revoke agent credentials in agents.py (→ database in production)

Recordkeeper Duties (handled by plan sponsor in current scope):
  9. Participant account data management
     - View and update vested balances, employment status, loan records
     - Manage investment elections per participant

  10. Disbursement confirmation
      - After approving a disbursement request (hardship, in-service):
        entry moves to approved_awaiting_bank_details
      - Participant then provides bank details via POST /transactions/disburse
      - Sponsor confirms funds were sent; balance updated manually

  11. Account lifecycle management
      - Onboarding new participants
      - Processing terminations (vesting cutoff, forfeiture)
      - QDRO alternate payee account setup

  NOTE: Phase 5+ will replace items 9–11 with automated external SFTP
        (Fidelity/Vanguard/Empower nightly balance file + outbound instructions).
        Until then, plan sponsor handles these manually.
```

### Running the CrewAI CLI

```bash
# Requires ANTHROPIC_API_KEY in .env
source .venv/bin/activate
python demo/crew_cli.py
```

Two active roles in current scope:
1. **Participant** — loans, deferrals, investments, distributions (natural language)
2. **Plan Sponsor** — review queue, blackouts, audit log, all recordkeeper duties (command-style)

(Investment Advisor exists in the codebase but is out of scope for current build.)

See [CLI_GUIDE.md](CLI_GUIDE.md) for a full reference of every action, the confirm/cancel flow, and mock data.

---

## Phase Status

```
Phase 1 · Core Engine          ✅ COMPLETE
├── Pydantic v2 models (PLAP, FAP, PAAP)
├── 12-rule FAP compliance engine — pure Python, fail-fast
├── JWT token issuance + single-use validation
├── Mock data — 2 plans, 4 participants, 4 agents
├── 87 pytest tests — every rule, pass + fail
└── Demo script — 3 loan scenarios

Phase 2 · Data Layer           ✅ COMPLETE
├── PostgreSQL schema — 11 base tables
├── data/db.py — full DB layer (reads + writes, graceful fallback)
└── Alembic migration 001 — base schema applied

Phase 3 · CrewAI + LLM         ✅ COMPLETE
├── 9 CrewAI tools wrapping PLAP/FAP/PAAP + documents
├── ParticipantCrew (4 agents), SponsorCrew, AdvisorCrew
│   ParticipantCrew agents:
│   ├── Intent Agent — natural language parsing, response formatting (no tools)
│   ├── Data Agent — read-only: GetPlanRules, GetFundLineup, GetParticipantSummary, GetLoanHeadroom
│   ├── Compliance Agent — RunComplianceCheckTool only (never touches data or execution)
│   └── Participant Agent — ExecuteTransactionTool only (write-only, post-FAP-token)
├── Crew router (crew/router.py)
├── Interactive CLI (demo/crew_cli.py)
├── Supervised confirm/cancel flow
├── Graceful API error handling
├── All 10 action types demoable
├── Live streaming display — step headers + per-tool output + 12-rule trace
├── Sponsor fast-path (instant reads without LLM: queue / audit / blackout)
├── Role switching via 'back' command — no Ctrl+C restart
├── Document upload system (hardship + QDRO)
│   ├── data/sample_docs/ — 5 pre-filled demo documents
│   ├── crew/tools/document_tools.py — UploadDocumentTool, GetDocumentsTool, verify_document()
│   ├── CLI: doc upload prompt after hardship/QDRO queue (sample / file path / skip)
│   ├── CLI: sponsor 'docs <entry_id>' command to view documents
│   └── CLI: Approve blocked for hardship/QDRO until verified docs on file
└── LLM document verification (Claude Haiku) — checks type, fields, legitimacy, participant name

Phase 4 · FastAPI Endpoints    ✅ COMPLETE
├── POST /auth/login, GET /meta/*
├── POST /chat (SSE streaming)
├── GET/POST /transactions/pending, confirm, cancel
├── POST /transactions/disburse (bank details — never stored)
├── POST /documents/upload (.txt/.pdf/.docx), GET /documents/{id}
├── GET/POST /queue, /queue/{id}/approve-docs, approve, deny
└── GET /admin/audit, POST /admin/blackout

Phase 5 · External Recordkeeper   ⏳ OUT OF SCOPE (plan sponsor handles manually now)
  When needed: SFTP with Fidelity / Vanguard / Empower
  Inbound: nightly balance file → PostgreSQL participants table
  Outbound: instruction file → ACH disbursement to participant's bank

Phase 6 · PostgreSQL Wiring    ✅ COMPLETE
├── Migration 002 — transactions, review_queue, documents tables (Alembic)
├── fap_audit_log — every FAP decision written to DB (audit bug fixed)
├── fap_tokens — issued + atomically consumed via PostgreSQL (saga rollback wired)
├── transactions — every PAAP execution recorded with action, amount, token_id
├── review_queue — DB-backed (JSON fallback if DATABASE_URL not set)
├── documents — DB-backed with MinIO object_key (JSON fallback)
├── vested_balance — decremented after every disbursement via DB
├── participant_loans — loan record created on every approved loan_initiation
├── Document verification — LLM checks participant name against name on document
└── MinIO — document bytes stored in S3-compatible object storage

Phase 7 · Production Hardening  ⏳ REMAINING
├── UI — web portal (THREE portals — see UI section below)
├── Redis — see full explanation below
├── Notifications — email/webhook when queue entry submitted (see below)
├── Audit export — GET /admin/audit/export.csv for DOL downloads (see below)
└── PII encryption at rest (PostgreSQL column-level encryption)
```

---

## Phase 7 Remaining Work — Full Explanation

### Redis

**What Redis is**
Redis is an in-memory key-value store that runs as a separate process alongside the API server.
Unlike a Python dict (which lives inside the server process), Redis survives server restarts
and is shared across multiple server instances (if you ever scale to 2+ servers).
It has native TTL support — you store a key with an expiry and it auto-deletes. No cleanup job needed.
It is the standard solution for short-lived durable state: session tokens, rate limiting, queues, ephemeral locks.

**What we are currently using without Redis (the problem)**
Right now, three things live as plain Python in-process variables:

| Variable | File | Type | What it holds |
|---|---|---|---|
| `supervised_pending` | `api/routes/transactions.py` | `dict` | Pending supervised transactions (loan initiation, deferral to 0%) — holds the FAP token until participant confirms or cancels via `/transactions/confirm` or `/transactions/cancel` |
| `disbursement_pending` | `api/routes/transactions.py` | `dict` | Queue entries in `approved_awaiting_bank_details` state — holds the FAP token between sponsor approval and participant bank details submission via `/transactions/disburse` |
| `consumed_tokens` | `agents/fap/tokens.py` | `set` | Set of JWT token IDs that have already been used — prevents the same FAP token being submitted twice (double-spend protection) |

**Why this is a problem**
If the API server restarts (crash, redeploy, scaling event):
- `supervised_pending` is wiped → participant who was mid-confirm loses their pending loan; they'd have to re-chat
- `disbursement_pending` is wiped → participant whose hardship was sponsor-approved can no longer disburse
- `consumed_tokens` is wiped → a previously used FAP token could be replayed immediately after restart

**What Redis fixes**
All three variables become Redis keys with a TTL matching the FAP token expiry (15 minutes):
```
supervised_pending[token_id]   → Redis HASH, EX 900
disbursement_pending[entry_id] → Redis STRING, EX 900
consumed_tokens[token_id]      → Redis SET member (SADD + TTL)
```
After a server restart, the state is still in Redis. Participants mid-flow are unaffected.

**Why Redis and not PostgreSQL for these?**
These are ephemeral state — they expire in 15 minutes naturally.
Putting them in PostgreSQL would work but requires periodic cleanup jobs and adds load to the
transactional DB. Redis handles TTL natively, is much faster for these tiny reads/writes,
and is the industry standard for this exact pattern (token state, session locks).

**Files to change when implementing:**
- `api/routes/transactions.py` — replace `supervised_pending` and `disbursement_pending` dicts
- `agents/fap/tokens.py` — replace `consumed_tokens` set and `_pending_tokens` set
- Add `redis` to `requirements.txt`, add `REDIS_URL` to `.env.example`

---

### Notifications

**What it is**
Currently the plan sponsor must actively poll `GET /queue` to see if a new human_review entry arrived.
There is no push — no email, no webhook, nothing fires when a participant submits a hardship request.

**What to build**
Hook into `data/review_queue.py → enqueue()`. After writing the entry to DB, fire an async notification:
- **Email**: send to sponsor's email (plan → sponsor_email field) via SendGrid or SMTP
  Subject: `[Aldergate] New {action} request from {participant_id} — requires your approval`
- **Webhook** (optional): POST to a configured `SPONSOR_WEBHOOK_URL` with the queue entry JSON

**Why it matters for ERISA compliance**
ERISA has time limits on some approvals (QDRO: 18 months to qualify, ERISA § 206(d)).
If the sponsor doesn't know a request arrived, the clock still runs.

**Files to change:**
- `data/review_queue.py` — add `_send_notification(entry)` call inside `enqueue()`
- New file: `api/notifications.py` — email/webhook dispatch logic
- Add `SPONSOR_EMAIL`, `SMTP_HOST` (or `SENDGRID_API_KEY`), `SPONSOR_WEBHOOK_URL` to `.env.example`

---

### Audit Export

**What it is**
ERISA § 107 requires the plan to retain FAP audit records for 6 years and produce them on DOL request.
Currently the audit log is in PostgreSQL (`fap_audit_log` table) and readable via `GET /admin/audit`.
But DOL auditors ask for a file — not a REST API call.

**What to build**
`GET /admin/audit/export.csv` — streams the full `fap_audit_log` table as a CSV download.
Optionally add `?from=2025-01-01&to=2025-12-31` date range filters.

**Files to change:**
- `api/routes/admin.py` — add one new route using Python `csv.DictWriter` + `StreamingResponse`
- No schema changes needed — data is already in `fap_audit_log`

---

### UI (the largest remaining item)

See the UI section elsewhere in this document for the three portals breakdown.
Redis, notifications, and audit export are all independent of the UI and can be built in any order.

---

## Work Log — What Was Done (2026-07-01 / 2026-07-02)

All Phase 3 polish — no new phases, only hardening the existing demo:

**Payload key bug fixes (compliance.py)**
- `deferral_pct` / `new_deferral_pct` mismatch — LLM was sending the wrong key, compliance read 0
- `rollover_402f_notice_confirmed` / `rollover_notice_issued` mismatch — separation always denied
- Fixed with safe fallback pattern (`if "key" in payload else payload.get("fallback", default)`)
- `or` pattern was unsafe for False/0 values — used `in` check instead

**PART-002 updated (mock_participants.py)**
- Changed employment_status from active → retired
- Added rmd_required=True, rmd_amount_current_year=$16,800
- Separation distribution and RMD are now demoable
- 86 tests still pass (fixtures use deep copies, employment_status set explicitly where needed)

**LLM instructions updated (fap_tools.py, participant_crew.py)**
- Added all 10 action types with correct payload key names
- Added note: if rmd_required=True in participant summary, include rmd_satisfied_for_year=true
- Valid fund IDs added to investment_reallocation description

**Live streaming display (crew_cli.py, tool_logger.py)**
- tool_logger.py: added set_live() / clear_live() — live callback fires synchronously on record()
- crew_cli.py: _make_live_fn() writes to sys.__stdout__ (bypasses redirect_stderr context)
- Step headers printed before crew runs; tool call lines appear as each tool fires
- RunComplianceCheck triggers _show_compliance_trace_to() — shows all 12 rules pass/fail inline
- Denial shows which rule failed and "Rules N–12 not evaluated (fail-fast)"

**Queue persistence (review_queue.py)**
- Added _QUEUE_FILE = data/review_queue_state.json
- _load() on module import; _save() after enqueue(), approve(), deny()
- Queue survives Ctrl+C and full process restarts

**Sponsor fast-path (crew_cli.py)**
- "queue" → GetPendingReviewsTool() directly, no LLM
- "audit" → GetAuditLogTool() directly
- "blackout status" → ManageBlackoutTool(operation='status') directly
- Sponsor data reads are now instant

**Role switching (crew_cli.py)**
- Main menu loop: selecting a role runs that session; typing 'back' returns to menu
- No restart needed to switch between Participant and Plan Sponsor

---

## Phase 4 — FastAPI REST Endpoints (COMPLETE)

FastAPI sits on top of the existing compliance engine. The CLI remains the demo interface; FastAPI is the production-facing API.

**Built endpoints:**

```
POST /auth/login                    → JWT session token (1hr TTL)
GET  /meta/participants             → demo participant list
GET  /meta/plans                    → demo plan list
GET  /meta/actions                  → valid action types + example messages

POST /chat                          → SSE streaming (participant or sponsor message)
GET  /transactions/pending          → supervised transaction awaiting confirm
POST /transactions/confirm          → confirm supervised (disbursement → awaiting_bank_details)
POST /transactions/cancel           → discard supervised pending
POST /transactions/disburse         → provide bank details → PAAP executes
                                      { routing_number, account_number, account_type, entry_id? }
                                      no entry_id = supervised flow
                                      entry_id = human_review flow

POST /documents/upload              → upload hardship/QDRO supporting doc (multipart)
GET  /documents/{doc_id}            → view a single document

GET  /queue                         → pending sponsor review items
GET  /queue/{entry_id}              → single queue entry detail
GET  /queue/{entry_id}/docs         → documents for a queue entry
POST /queue/{entry_id}/approve-docs → sponsor approves documents (required for hardship/QDRO)
POST /queue/{entry_id}/approve      → sponsor approves request
                                      disbursement actions → approved_awaiting_bank_details
                                      other actions → approved (executes immediately)
POST /queue/{entry_id}/deny         → sponsor denies with reason

GET  /admin/audit                   → FAP audit log (all decisions, approved + denied)
POST /admin/blackout                → activate/deactivate blackout via SponsorCrew

GET  /health                        → server status check
```

**Auth:** JWT session tokens. `POST /auth/login` issues a 1hr token. All endpoints require `Authorization: Bearer <token>`.

**Key implementation detail:**
The disburse endpoint handles both flows from one endpoint. No `entry_id` = supervised (uses in-memory `_disbursement_pending`). With `entry_id` = human_review (uses FAP token stored in queue entry, status must be `approved_awaiting_bank_details`). Bank details never stored.

See [SWAGGER_GUIDE.md](SWAGGER_GUIDE.md) for step-by-step testing instructions.

---

## Phase 5 — External Recordkeeper Integration (Out of Scope Now)

**Current state:** Plan sponsor handles all recordkeeper duties manually. This is the correct approach for the current build — no external SFTP is needed until the product is deployed with a real recordkeeper.

**What "plan sponsor as recordkeeper" means today:**
- Participant data (balances, loans, elections) managed manually by sponsor via admin portal
- After approving a disbursement, participant provides bank details (POST /transactions/disburse) and the sponsor confirms funds were sent
- Balance updates done manually by sponsor

**When Phase 5 becomes relevant (not now):**

Before starting, confirm with lead:
1. Which recordkeeper? (Fidelity, Vanguard, Empower, or others)
2. File format? (NSCC standard, recordkeeper's proprietary spec, or CSV)
3. SFTP credentials and inbound drop schedule
4. Outbound instruction format
5. Whether they provide a sandbox/test environment

**What to build (Phase 5, future):**
```
data/ingestion/                    ← INBOUND (Recordkeeper → Aldergate)
├── sftp_watcher.py      ← polls SFTP, downloads nightly balance file
├── parser.py            ← parses recordkeeper format → Pydantic models
└── upsert.py            ← writes to PostgreSQL participants table

data/outbound/                     ← OUTBOUND (Aldergate → Recordkeeper)
├── instruction_sender.py ← triggered after PAAP executes
└── instruction_log.py   ← audit trail for outbound files
```

---

## Phase 6 (PostgreSQL Write Wiring — COMPLETE)

Phase 2 wired PostgreSQL reads. Phase 6 added all write paths:
- Alembic migration 002 — `transactions`, `review_queue`, `documents` tables created
- `fap_audit_log` — every FAP decision written to DB (approved + denied)
- `fap_tokens` — issued and atomically consumed via PostgreSQL (saga rollback wired)
- `transactions` — every PAAP execution recorded (action, amount, token_id)
- `review_queue` — DB-backed; JSON fallback if DATABASE_URL not set
- `documents` — DB-backed with MinIO object_key; JSON fallback
- `vested_balance` — decremented in PostgreSQL after every disbursement
- `participant_loans` — loan record created on every approved loan_initiation
- Document verification — LLM checks participant name against name on document
- Graceful fallback pattern throughout — all DB calls in try/except; in-memory if DB absent

---

## Documentation Status

| Document | What it covers | Status |
|---|---|---|
| [CLAUDE.md](CLAUDE.md) | Full architecture, ERISA concepts, file structure, critical rules | Current |
| [WORKFLOW2.md](WORKFLOW2.md) | Orchestration spec, agent definitions, tool matrix, phase status | Current |
| [SWAGGER_GUIDE.md](SWAGGER_GUIDE.md) | Step-by-step API testing guide for every endpoint | Current |
| [DEMO_GUIDE.md](DEMO_GUIDE.md) | All demo scenarios, every participant × action, sponsor flows | Current |
| [CLI_GUIDE.md](CLI_GUIDE.md) | Every CLI action, confirm/cancel flow, error messages | Current |

**Current build is complete through Phase 6.** Phases 1–6 are done. The full participant → compliance → supervised confirm / sponsor approve → document verification → bank details → disbursement flow is wired end to end with PostgreSQL persistence throughout.

**What is remaining (Phase 7):**
- Redis — swap in-memory token dicts for a persistent cache that survives restarts
- Notifications — email/webhook when a new review queue entry arrives
- Audit CSV export — GET /admin/audit/export.csv for DOL compliance downloads
- UI — three web portals (participant self-service, sponsor admin, advisor)
- Phase 5: external recordkeeper SFTP — plan sponsor handles manually until then

**Before Phase 5 (external recordkeeper) becomes relevant, confirm:**
- Which recordkeeper? (Fidelity, Vanguard, Empower, or others)
- Outbound file format / data dictionary
- Inbound balance file format / data dictionary
- SFTP credentials and drop schedule
- Whether they provide a sandbox/test environment
