# Aldergate — Path B: LLM + CrewAI Query-Driven Workflow
## Industry-Grade Specification — Agents · Tasks · Tools · Flow

---

## What We Are Building

A **401(k) administration platform** called **Aldergate** — a **TPA (Third-Party Administrator)** built with CrewAI + Claude (LLM) + PLAP/FAP/PAAP (pure-Python compliance engine).

When an employee wants to do something with their retirement account — take a
loan, change contributions, make a withdrawal — strict government regulations
(ERISA laws) must be checked first. Companies currently do this manually or
with outdated software. Aldergate automates the compliance checks, routes
requests to the right people, maintains the audit trail required by law, and
also acts as its own **Recordkeeper** — the module that holds the investment
ledger, processes ACH disbursements, and updates balances after settlement.
Unlike traditional TPAs that rely on Fidelity/Vanguard/Empower, Aldergate
owns the full stack from compliance engine to money movement.

**Users:**
- **Participant (employee)** — self-service: loans, deferrals, distributions, investments
- **Plan Sponsor (HR/employer)** — approves requests, manages plan rules and blackouts, owns the audit log
- **Investment Advisor** — submits investment recommendations for clients

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
│  Currently: PostgreSQL reads (data/db.py — Phase 2 done)    │
│             review queue → JSON file (persists to disk)     │
│  Phase 4:   REST API wired to same compliance engine        │
│  Phase 6:   PostgreSQL writes, Redis token store, PII enc   │
│                                                             │
│  STATUS: ✅ Reads wired (Phase 2). Writes pending Phase 6   │
└──────────────────────────┬──────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────┐
│  LAYER 5 — Recordkeeper (Fidelity / Vanguard / Empower)      │
│  External custodian — holds the real fund units and money   │
│                                                             │
│  OUTBOUND (Aldergate → Recordkeeper):                        │
│    PAAP approved → Aldergate generates instruction file      │
│    → SFTP to Recordkeeper                                    │
│    Recordkeeper liquidates fund units, initiates ACH         │
│    → participant's external bank in 3–5 business days       │
│                                                             │
│  INBOUND (Recordkeeper → Aldergate):                         │
│    Nightly SFTP file drop → data/ingestion/ → PostgreSQL    │
│    Updates vested_balance, elections, loan status            │
│                                                             │
│  STATUS: ⏳ Not built — Phase 5                             │
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
[Phase 4] REST API approve endpoint:
System re-issues fresh FAP token (original expired — 5min TTL)
Same 12 rules re-run with same payload
New token → PAAP executes → writes to PostgreSQL
         │
         ▼
[Phase 5] PAAP writes instruction to Aldergate PostgreSQL
Aldergate generates outbound instruction file (recordkeeper's format)
→ SFTP to Recordkeeper (Fidelity / Vanguard / Empower)
         │
         ▼
Recordkeeper receives instruction file
Liquidates fund units from participant's 401k account
Generates NACHA file → ACH to employee's external bank (3–5 days)
Withholds mandatory 20% federal tax (IRC §3405) if distribution
Issues 1099-R at year end
         │
         ▼
[Phase 5] Recordkeeper nightly SFTP file drop
Aldergate ingestion pipeline → PostgreSQL participants updated
vested_balance reflects reality after recordkeeper confirms
```

**What is complete today (demo-ready):** Everything from employee types to sponsor approves to employee sees status.
**What is pending:** The final PAAP execution after approval (Phase 4), real balance updates (Phase 6), actual money movement (Phase 5).

---

## Current Build Status

```
✅ Built and demo-ready
   Layer 2: Intent Agent, Data Agent, Compliance Agent (CrewAI + Claude)
   Layer 3: PLAP, FAP (12 rules), PAAP — pure Python, 87 tests
   Layer 1: CLI — participant + sponsor + advisor sessions
            Live streaming display, fast-path commands, role switching
            Review queue persists to disk (review_queue_state.json)

⏳ Not yet built
   Layer 4: PostgreSQL wiring (Phase 6) — schema ready, mocks in place
   Layer 1+: REST API (Phase 4), web portal (Phase 7+)
   Layer 5: Recordkeeper SFTP integration (Phase 5)
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

### `supervised` — show summary first, wait for confirm

Big money or hard-to-reverse actions. The participant must see exactly what
they're agreeing to before anything executes. Token is held until they confirm.

```
Example: participant requests a $20,000 loan

Token issued → Intent Agent shows summary → participant types "confirm"
             → PAAP executes → done

             If participant types "cancel" → token discarded → nothing moves

Participant sees:
  "Your loan of $20,000 has been approved.
   · Monthly payment: $387/month for 60 months
   · Interest rate: 6.5% (paid back into your account)
   · Processing: 3–5 business days

   Type 'confirm' to proceed or 'cancel' to stop."
```

### `human_review` — admin must approve before anything executes

Legally required human oversight. PAAP cannot execute these no matter what.
The token goes into a queue. A plan administrator reviews it and approves it
manually. Only then does PAAP write anything.

For **hardship_distribution** and **qdro**: the participant must upload supporting
documents BEFORE the sponsor can approve. The Approve command is blocked
until at least one verified document is on file for that queue entry.

```
Example: participant requests a hardship withdrawal

FAP runs 12 rules → approved → autonomy=human_review
Token issued → request queued (status: pending)
             ↓
Participant uploads medical bill
Claude Haiku verifies document → verified ✓
             ↓
Sponsor types "docs AB064BBC" → reads document content + LLM verification note
Sponsor types "approve doc AB064BBC" → explicitly approves the document (Step 2)
Sponsor types "Approve AB064BBC — valid docs" → request approved (Step 3, only allowed after Step 2)
             ↓
[Phase 4] System re-issues fresh FAP token (original 5-min TTL expired)
Same 12 rules re-run → new token → PAAP executes

Participant sees:
  "Your hardship withdrawal request has been submitted for review.
   A plan administrator will contact you within 2-3 business days.
   Reference number: HW-2024-0042"
```

**Why the token is re-issued on approval:** FAP tokens have a 5-minute TTL in
production (prevents replay attacks). Sponsor reviews happen hours or days later.
When the sponsor approves, Phase 4 re-runs the same 12 rules with the same
payload to get a fresh token — this is the `human_review → approval → re-issue
→ PAAP execute` loop. The original FAP audit entry is the compliance record;
the re-issue is just a fresh execution credential.

### Summary table

| Level | When FAP assigns it | PAAP executes | Who triggers execution |
|---|---|---|---|
| `full` | Safe + reversible (deferral increase, rebalance) | Immediately | System — automatic |
| `supervised` | Big + irreversible (any loan, deferral to 0%) | After confirm | Participant types "confirm" |
| `human_review` | Law requires oversight (hardship, separation, QDRO, beneficiary) | After admin approves | Plan administrator |

**The token is issued in all 3 cases.** FAP already said "yes, ERISA-legal."
The autonomy level only controls who pulls the trigger and when.

**Documents for human_review:**
- `hardship_distribution` — participant must upload docs (medical bill, eviction notice, tuition invoice, etc.)
- `qdro` — participant must upload signed court order
- All other human_review actions (beneficiary, separation, rmd) — no doc requirement in current demo

```
full          = legal + safe + reversible  → just do it
supervised    = legal + big + irreversible → make sure they meant it
human_review  = legal + law requires admin → human must sign off
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
                                           │              │  participant types confirm
                                           │              └──► [EXECUTING] → [RESPONSE] → [IDLE]
                                           │              │  participant types cancel
                                           │              └──► [RESPONSE] → [IDLE]
                                           │
                                           └── APPROVED / human_review
                                                   → [QUEUING] → [AWAITING_DOCUMENTS] → [RESPONSE] → [IDLE]
                                                          ↑ CLI prompts doc upload immediately after queue
                                                            participant uploads → LLM verifies → stored
                                                            sponsor cannot approve until verified docs on file
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

**Source of truth: Aldergate Recordkeeper (built-in module)**

We build our own recordkeeper. Balances, elections, loan status — all live in our
own PostgreSQL, maintained by the Aldergate Recordkeeper's nightly settlement job.
No external Fidelity/Vanguard/Empower. We are both the TPA and the recordkeeper.

```
┌──────────────────────────────────────────────────────────┐
│  ALDERGATE RECORDKEEPER  (built-in module — Phase 5)      │
│                                                          │
│  Instruction Receiver   ← receives PAAP write commands   │
│  Investment Ledger      ← tracks holdings per participant │
│  Trade Engine           ← processes fund elections        │
│  ACH Processor          ← sends funds to external banks   │
│  Nightly Settlement     ← recalculates vested_balance    │
│                                                          │
│  Internal communication: direct PostgreSQL / service call │
│  External ACH: NACHA file to participant's bank (3–5 days)│
└───────────────────────┬──────────────────────────────────┘
                        │
                        │  after nightly settlement runs
                        ▼
           data/ingestion/ (Phase 5)
           settlement_job.py → upsert
                        │
                        │  upsert
                        ▼
              Our PostgreSQL
              participants table
              participant_loans
              participant_investment_elections
                        │
                        ▼
      GetParticipantSummaryTool → Data Agent → FAP
```

**PAAP always reads from our PostgreSQL** — that table is updated by the Aldergate
Recordkeeper's nightly settlement job. vested_balance is updated AFTER the
recordkeeper confirms funds have been sent, not at the time of the PAAP instruction.

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
ADMIN                              PARTICIPANT
(your team / HR)                   types query in chatbot
       │                                  │
       │ fills plan form                  │
       ▼                                  ▼
 POST /admin/plans              Aldergate TPA (CrewAI + Claude)
 Phase 4 dashboard              PLAP/FAP/PAAP compliance engine
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
                 ▼ [Phase 5: write-back]
     ALDERGATE RECORDKEEPER (built-in module) receives instruction
     ├── Investment Ledger updated
     ├── ACH Processor sends funds to participant's external bank (3–5 days)
     └── Nightly Settlement Job → PostgreSQL vested_balance updated
```

---

### Dev vs Production — What Changes

| Layer | Dev (now) | Production |
|---|---|---|
| Plan data | `plans.py` → PostgreSQL reads (Phase 2 done) | PostgreSQL via psycopg2 |
| Participant data | `participants.py` → PostgreSQL reads (Phase 2 done) | PostgreSQL via psycopg2 (synced from recordkeeper) |
| FAP token store | Python `set` in memory | Redis (TTL-based, survives restarts) |
| External API | None | GraphQL API (admin dashboard + chat UI) |
| Participant sync | None | Phase 5 SFTP/API ingestion pipeline (recordkeeper → Aldergate) |

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

### What Is NOT a Portal (automated, no UI needed)

```
Aldergate          ← Recordkeeper nightly settlement job (Phase 5)
Recordkeeper         runs automatically after market close, no human in the loop
                     no external SFTP — internal module, owned by Aldergate

FAP token store    ← Redis in production, no UI
                     tokens expire in 5 minutes, self-cleaning

Audit log          ← PostgreSQL append-only table
                     admin reads it through Portal 2
                     DOL auditor gets a file export, not a login
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
│  RECORDKEEPER  (Fidelity / Vanguard / Empower)                        │
│  External custodian — holds real balances, fund units, loan status   │
│  NOT part of Aldergate. Two-way SFTP communication (Phase 5).        │
│                                                                      │
│  INBOUND → Aldergate (nightly at ~10pm ET):                          │
│    SFTP file drop → data/ingestion/ → PostgreSQL                     │
│    participants ← vested_balance, elections, loans, employment        │
│  (Dev: mock_participants.py used until Phase 5 is built)             │
│                                                                      │
│  OUTBOUND ← Aldergate (on every approved transaction):               │
│    PAAP executes → Aldergate generates instruction file               │
│    → SFTP to Recordkeeper                                            │
│    Recordkeeper liquidates fund units → generates NACHA file         │
│    → ACH to participant's external bank (3–5 business days)          │
│    Next nightly inbound file → PostgreSQL vested_balance updated     │
└──────────────────────────────┬───────────────────────────────────────┘
                               │ participants table populated nightly (inbound)
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
│  │ → participant types "confirm"                            │
│  │ → confirm_handler.py re-invokes Data Agent               │
│  │ → ExecuteTransactionTool called with fap_token           │
│  │ → PAAP validates token → writes to PostgreSQL            │
│  └──────────────────────────────────────────────────────────┘
│
│  ┌──────────────────────────────────────────────────────────┐
│  │ autonomy = human_review                                  │
│  │ Tools: QueueForReviewTool                                │
│  │        creates pending_review record in PostgreSQL       │
│  │        notifies plan administrator                       │
│  │ Output: QueueReceipt                                     │
│  │         { "reference_number": "HW-2024-0042",            │
│  │           "estimated_review_days": 3 }                   │
│  │ PAAP does NOT execute — admin must approve first         │
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
    · Processing: 3–5 business days to your bank on file

    Type 'confirm' to proceed or 'cancel' to stop."
─────────────────────────────────────────────────────────────────

[Phase 5 — OUTBOUND to Recordkeeper, after participant confirms]

Step 1 — PAAP writes instruction to Aldergate PostgreSQL
  "PART-008: loan_initiation $20,000 approved — fap_token ABC"

Step 2 — Aldergate generates outbound instruction file
  instruction_sender.py builds file in recordkeeper's format
  → SFTP upload to Recordkeeper (Fidelity / Vanguard / Empower)

Step 3 — Recordkeeper processes instruction file
  · Reads "PART-008 loan $20,000 — disburse to routing/account on file"
  · Liquidates $20,000 worth of fund units from participant's 401k
  · Generates NACHA file → ACH to participant's external bank
  · 3–5 business days for funds to appear in participant's checking account
  · For distributions: withholds mandatory 20% federal tax (IRC § 3405)
  · Issues 1099-R at year end for taxable events

Step 4 — Recordkeeper nightly SFTP file drop (next ~10pm ET)
  Aldergate ingestion pipeline (sftp_watcher.py → parser → upsert)
  → PostgreSQL vested_balance updated to reflect funds sent
  Participant sees updated balance on next login
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

### `supervised` — show summary first, wait for confirm

Big money or hard-to-reverse actions. The participant must see exactly what
they're agreeing to before anything executes. Token is held until they confirm.

```
Example: participant requests a $20,000 loan

Token issued → Intent Agent shows summary → participant types "confirm"
             → PAAP executes → done

             If participant types "cancel" → token discarded → nothing moves

Participant sees:
  "Your loan of $20,000 has been approved.
   · Monthly payment: $387/month for 60 months
   · Interest rate: 6.5% (paid back into your account)
   · Processing: 3–5 business days

   Type 'confirm' to proceed or 'cancel' to stop."
```

### `human_review` — admin must approve before anything executes

Legally required human oversight. PAAP cannot execute these no matter what.
The token goes into a queue. A plan administrator reviews it and approves it
manually. Only then does PAAP write anything.

```
Example: participant requests a hardship withdrawal

Token issued → request queued → admin reviews within 2-3 business days
             → admin approves → PAAP executes

Participant sees:
  "Your hardship withdrawal request has been submitted for review.
   A plan administrator will contact you within 2-3 business days.
   Reference number: HW-2024-0042"
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

### What the Recordkeeper Is (and Is Not)

The **Recordkeeper** (Fidelity, Vanguard, Empower) is:
- The external custodian that actually holds participant fund units and money
- NOT a conversational agent or portal user
- A two-way automated data partner: Aldergate sends outbound instructions,
  recordkeeper sends back nightly balance files

There is no RecordkeeperCrew. There is a Phase 5 two-way SFTP pipeline:
```
OUTBOUND (Aldergate → Recordkeeper):
  PAAP executes → instruction_sender.py builds file → SFTP to recordkeeper
  Recordkeeper liquidates fund units → NACHA → participant's external bank

INBOUND (Recordkeeper → Aldergate):
  Recordkeeper nightly SFTP drop → sftp_watcher.py → parser → upsert
  → PostgreSQL participants table updated
  CrewAI crews read from this table at query time
```

### Plan Sponsor Full Duties (beyond plan onboarding)

```
Administrative duties in SponsorCrew:
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
```

### Running the CrewAI CLI

```bash
# Requires ANTHROPIC_API_KEY in .env
source .venv/bin/activate
python demo/crew_cli.py
```

Three roles at the menu:
1. **Participant** — loans, deferrals, investments, distributions (natural language)
2. **Plan Sponsor** — review queue, blackouts, audit log (command-style)
3. **Investment Advisor** — submit reallocation/deferral recommendations for a client

See [CLI_GUIDE.md](CLI_GUIDE.md) for a full reference of every action, the confirm/cancel flow, and mock data.

---

## Phase Status

```
Phase 1 · Core Engine          ✅ COMPLETE
├── Pydantic v2 models (PLAP, FAP, PAAP)
├── 12-rule FAP compliance engine — pure Python
├── JWT token issuance + single-use validation
├── Mock data — 2 plans, 5 participants, 4 agents
├── 86 pytest tests — every rule, pass + fail
└── Demo script — 3 loan scenarios

Phase 2 · Data Layer           ✅ COMPLETE
├── PostgreSQL schema — 11 tables
├── data/db.py — real DB layer (same interface as mocks)
└── Alembic migration — alembic upgrade head

Phase 3 · CrewAI + LLM         ✅ COMPLETE
├── 8 CrewAI tools wrapping PLAP/FAP/PAAP
├── ParticipantCrew, SponsorCrew, AdvisorCrew
├── Crew router (crew/router.py)
├── Interactive CLI (demo/crew_cli.py)
├── Supervised confirm/cancel flow
├── Graceful API error handling
├── All 10 action types demoable (payload key bugs fixed)
├── Live streaming display — step headers + per-tool output + 12-rule trace
├── Queue persistence to disk (survives restarts)
├── Sponsor fast-path (instant reads without LLM: queue / audit / blackout)
├── Role switching via 'back' command — no Ctrl+C restart
├── PART-002 updated to retired + rmd_required (separation + RMD now demoable)
├── Document upload system (hardship + QDRO)
│   ├── data/document_store.py — JSON-backed document records
│   ├── data/sample_docs/ — 5 pre-filled demo documents
│   ├── crew/tools/document_tools.py — UploadDocumentTool, GetDocumentsTool, verify_document()
│   ├── CLI: doc upload prompt after hardship/QDRO queue (sample / file path / skip)
│   ├── CLI: sponsor 'docs <entry_id>' command to view uploaded documents
│   └── CLI: Approve blocked for hardship/QDRO until verified docs on file
└── LLM-based document verification (Claude Haiku, direct API call, not CrewAI)

Phase 4 · FastAPI Endpoints    ⏳ NEXT
Phase 5 · Recordkeeper SFTP Integration   ⏳ PENDING
Phase 6 · Production Hardening ⏳ PENDING
```

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

## Upcoming Work — Phase 4 (FastAPI REST Endpoints)

Phase 4 builds the REST API layer that sits on top of the existing compliance engine. The CLI stays as the demo interface; FastAPI is the production-facing API that the web portal (Path A) and external integrations will call.

**What to build:**

```
POST /participant/{participant_id}/loan             → runs FAP, returns FapResult
POST /participant/{participant_id}/deferral         → runs FAP, returns FapResult
POST /participant/{participant_id}/hardship         → runs FAP, routes to queue
POST /participant/{participant_id}/confirm          → executes supervised pending
POST /participant/{participant_id}/distribution     → separation / in-service
POST /participant/{participant_id}/rmd              → RMD processing
POST /participant/{participant_id}/reallocation     → investment reallocation
POST /participant/{participant_id}/beneficiary      → beneficiary update
POST /participant/{participant_id}/address          → address update (full autonomy)

GET  /sponsor/{plan_id}/queue                      → pending review items
POST /sponsor/{plan_id}/approve/{entry_id}         → approve + re-issue token + execute (blocks if no verified docs for hardship/QDRO)
POST /sponsor/{plan_id}/deny/{entry_id}            → deny with reason
GET  /sponsor/{plan_id}/audit                      → FAP audit log
POST /sponsor/{plan_id}/blackout                   → activate/deactivate

POST /participant/{participant_id}/documents       → upload supporting doc for a queue entry (hardship/QDRO)
GET  /participant/{participant_id}/documents/{entry_id} → list docs for a queue entry
GET  /sponsor/{plan_id}/documents/{entry_id}       → sponsor view: docs for a queue entry

GET  /plan/{plan_id}/rules                         → plan configuration
GET  /participant/{participant_id}/summary         → account summary (no PII)
```

**Auth pattern for Phase 4:**
- Each request carries `agent_id` in the header (maps to AGENT_REGISTRY)
- FastAPI middleware validates `agent_id` exists and has scope for the requested action
- No new auth system needed — FAP Rule 1 already checks this; middleware just rejects before FAP runs

**Key wiring task:**
The approve endpoint must re-issue a fresh FAP token (the original 5-min token expired) before calling PAAP to execute. This is the `human_review → approval → re-issue → PAAP execute` loop described in DEMO_GUIDE.md Scenario 5.

**What does NOT change:**
- PLAP, FAP, PAAP code is unchanged
- The 12 compliance rules are unchanged
- Mock data can stay — FastAPI just calls the same functions the CLI calls

---

## Upcoming Work — Phase 5 (Recordkeeper SFTP Integration)

Two-way SFTP pipeline between Aldergate and the external recordkeeper
(Fidelity, Vanguard, Empower — whichever the plan sponsor uses).

**Before starting Phase 5, confirm with lead:**
1. Which recordkeeper? (Fidelity, Vanguard, Empower, or others)
2. File format? (NSCC standard, recordkeeper's proprietary spec, or CSV)
3. SFTP credentials and inbound drop schedule (most do nightly ~8–10pm ET)
4. Outbound instruction format — what fields the recordkeeper expects
5. Whether they provide a sandbox/test environment

**What to build:**
```
data/ingestion/                    ← INBOUND (Recordkeeper → Aldergate)
├── sftp_watcher.py      ← polls SFTP, downloads nightly balance file
├── parser.py            ← parses recordkeeper format → Pydantic models
├── validator.py         ← validates required fields, detects anomalies
└── upsert.py            ← writes to PostgreSQL participants table

data/outbound/                     ← OUTBOUND (Aldergate → Recordkeeper)
├── instruction_sender.py ← triggered after PAAP executes an approved txn
│                           builds instruction file in recordkeeper's format
│                           uploads via SFTP to recordkeeper's inbound folder
└── instruction_log.py   ← records every outbound file sent (audit trail)
```

**Full bidirectional flow:**
```
APPROVED TRANSACTION (outbound path):
  PAAP executes → writes to PostgreSQL
       │
       ▼
  instruction_sender.py
  builds instruction file: participant ID, action, amount, bank routing
       │
       ▼  SFTP upload
  RECORDKEEPER receives file
  · Liquidates fund units
  · Generates NACHA file → ACH to participant's external bank (3–5 days)
  · For distributions: withholds 20% federal tax (IRC § 3405)

NIGHTLY BALANCE SYNC (inbound path):
  Recordkeeper SFTP file drop (~10pm ET)
       │
       ▼
  sftp_watcher.py → parser.py → validator.py → upsert.py
       │
       ▼
  PostgreSQL participants updated
  (vested_balance reflects funds actually sent — delayed from instruction time)
```

---

## Phase 6 (Production Hardening — Database Wiring)

Phase 2 already wired PostgreSQL reads via `data/db.py`. Phase 6 adds:
- FAP token store: Python set → Redis (TTL enforcement survives restarts)
- Write-back paths: PAAP mutations written to PostgreSQL (currently in-memory only)
- PII encryption at rest, DOL compliance audit
- Alembic migration already tested — `alembic upgrade head` is ready

---

## Documentation Readiness for Lead

The three main documents are:
- **CLAUDE.md** — full architecture, all design decisions, ERISA concepts, file structure
- **WORKFLOW2.md** (this file) — orchestration spec, agent definitions, tool matrix, phase status
- **DEMO_GUIDE.md** — how to run the demo, all 9 scenarios, what to say

**Are they sufficient for Phase 4?**

Yes, for FastAPI endpoint design. The architecture is fully specified: every action type, every tool, the PLAP/FAP/PAAP flow, autonomy levels, and the human_review re-issue pattern. A developer can build Phase 4 from CLAUDE.md + WORKFLOW2.md without asking additional questions.

**What we still need from lead before Phase 5:**
- Which recordkeeper? (Fidelity, Vanguard, Empower, or others)
- Outbound file format / data dictionary (what fields the recordkeeper expects in instruction files)
- Inbound file format / data dictionary (participant balance file spec from recordkeeper)
- SFTP credentials and drop schedule (most do nightly drops at 8–10pm ET)
- Whether they provide a sandbox/test environment for integration testing

**What we still need before Phase 6:**
- PostgreSQL connection string for the production environment
- Whether Redis is already provisioned or needs to be set up
- Deployment target (AWS RDS, on-prem, managed container?)
