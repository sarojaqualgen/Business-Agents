# Aldergate — System Workflow

## The Three Non-LLM Agents

These are **deterministic Python code**, not AI. The word "agent" is the ERISA legal term.

| Agent | File | Question it answers | Touches participant data? |
|---|---|---|---|
| **PLAP** | `agents/plap/agent.py` | "What does this plan allow?" | ❌ Never |
| **FAP** | `agents/fap/compliance.py` | "Is this authorized?" | ⚠️ Read-only (inside authorize()) |
| **PAAP** | `agents/paap/agent.py` | "What can this participant do — and executes it." | ✅ Only agent that touches it |

---

## Full Request Flow — Loan Initiation

```
Browser
  │
  │  POST /chat/fast  { message, history }
  ▼
FastAPI  (api/routes/chat_fast.py)
  │
  │  get_participant_plan_id(participant_id)  ← PAAP — existence check
  │
  ▼
Claude Haiku  [LLM — intent classification only]
  │
  │  Returns: { transaction: { intent, params, missing }, data_question_type, conceptual_topic }
  │
  ├── data_question  ──► PAAP read fn  ──► PostgreSQL  ──► Haiku formats reply
  │
  ├── conceptual     ──► Haiku answers from FAP_RULES_TEXT context
  │
  └── loan_initiation
        │
        ▼
      paap.execute(participant_id, agent_id, "loan_initiation", payload)
        │
        │  Step 0 ── _load(participant_id)
        │            └─ data.db.get_participant()  →  PostgreSQL
        │            └─ raises ParticipantNotFound if missing
        │
        │  Layer 1 ── PLAP  (plap.query_capabilities)
        │             └─ Does plan allow loan_initiation?
        │             └─ raises PlanDoesNotSupportAction if not
        │
        │  Layer 2 ── FAP  (fap.authorize)
        │             └─ Runs 12 ERISA rules in order, fail-fast
        │             └─ raises UnauthorizedByFAP on any failure
        │             └─ Issues signed JWT on all-pass
        │             └─ Writes audit log for EVERY decision
        │
        │  Layer 3 ── autonomy decision
        │             ├─ full        →  _execute_write()  →  PostgreSQL
        │             ├─ supervised  →  return fap_token  →  caller stores it
        │             └─ human_review → return fap_token  →  caller queues it
        │
        └─ Returns { autonomy_level, executed, fap_token }
              │
              ▼
          chat_fast.py
              │  set_supervised_pending(participant_id, fap_token, ...)
              │  Haiku writes confirmation reply
              └─ Returns { reply, autonomy: "supervised", transaction: {...} }
                    │
                    ▼
                Browser  ──  Confirm / Cancel dialog appears
```

---

## Supervised Loan — Confirm & Disburse Flow

Runs only when `autonomy_level == "supervised"` (e.g. loan initiation).

```
Browser  [Confirm clicked]
  │
  │  POST /transactions/confirm
  ▼
api/routes/transactions.py  confirm_transaction()
  │
  ├─ get_supervised_pending(participant_id)  ←  reads from memory dict
  │
  ├─ loan IS a disbursement action
  │   └─ move token to _disbursement_pending
  │   └─ return { status: "awaiting_bank_details" }
  │
  └─ non-disbursement (e.g. deferral to 0%)
      └─ paap.execute_confirmed()  ──►  _execute_write()  ──►  PostgreSQL
      └─ return { status: "executed" }

Browser  [Bank details submitted]
  │
  │  POST /transactions/disburse  { routing_number, account_number, account_type }
  ▼
api/routes/transactions.py  disburse_transaction()
  │
  └─ paap.execute_confirmed(participant_id, action, payload, fap_token)
        │
        │  1.  _load(participant_id)              ←  PAAP loads participant
        │  2.  validate_token(fap_token, ...)      ←  FAP cryptographic check
        │       └─ single-use: token consumed here, can never be reused
        │  3.  _execute_write(participant_id, plan_id, action, payload)
        │       └─ db.decrement_vested_balance()
        │       └─ db.create_loan_record()
        │       └─ db.record_transaction()
        │
        └─ Returns { executed: true, status: "executed" }
              │
              └─ _clear_disbursement_pending()
              └─ return { disbursement: { account_last4, estimated_arrival } }
```

---

## FAP — The 12 ERISA Rules

Runs in `agents/fap/compliance.py`. Fail-fast — stops at first violation.

| # | Rule | ERISA / IRC citation |
|---|---|---|
| 1 | Agent registered in registry | Internal |
| 2 | No active blackout period | § 101(i) |
| 3 | Participant eligibility met | § 410(a) |
| 4 | Vesting percentage sufficient | § 411 |
| 5 | Deferral within annual limits | § 402(g) / SECURE 2.0 Roth catch-up |
| 6 | RMD notice acknowledged if required | § 401(a)(9) |
| 7 | Loan within IRC § 72(p) cap | § 72(p) |
| 8 | Hardship criteria met | Reg § 1.401(k)-1(d)(3) |
| 9 | Distribution eligibility (age / separation) | § 401(a) |
| 10 | Rollover rules satisfied | § 402(c) |
| 11 | QDRO determination valid | § 206(d) |
| 12 | Assign autonomy level | Internal |

All 12 pass → signed JWT issued (HS256, single-use).
Any failure → `AuthorizationDenied`, audit log written, no token.

---

## PAAP — Read vs Write

### Reads (no FAP token required)

```
get_participant_summary(participant_id)   →  benefit statement snapshot
get_vesting_info(participant_id)         →  years of service, vested %
get_loan_headroom(participant_id)        →  IRC §72(p) max borrow amount only
get_rmd_info(participant_id)            →  RMD amount and due date
get_distribution_options(participant_id) →  available withdrawal types
get_participant_plan_id(participant_id)  →  plan_id only (existence check)
```

### Writes (always PAAP → PLAP → FAP → execute)

```
execute(participant_id, agent_id, action, payload)
  └─ full       →  _execute_write() immediately
  └─ supervised →  returns fap_token, caller stores it
  └─ human_review → returns fap_token, caller queues it

execute_confirmed(participant_id, action, payload, fap_token)
  └─ used by confirm/disburse endpoints
  └─ validates existing token then calls _execute_write()
```

### Security invariants (enforced by PAAP, never bypassed)

- Raw SSN never returned — only `ssn_hash`
- Date of birth never returned — FAP resolves age internally
- Marital status never returned — FAP handles QJSA internally
- Full balance only in participant summary (own benefit statement)
- Every write requires a valid, unexpired, single-use FAP token

---

## PLAP — Plan Read Functions

```
query_plan(plan_id)            →  full plan config
query_capabilities(plan_id)    →  what actions the plan supports
query_vesting(plan_id)         →  vesting schedule
query_fund_lineup(plan_id)     →  available fund options
query_blackout_status(plan_id) →  is plan in blackout?
```

Never holds participant data. Never modifies anything. Pure read path.

---

## Autonomy Levels

| Level | What PAAP does | Example actions |
|---|---|---|
| `full` | Executes write immediately | deferral increase, investment reallocation |
| `supervised` | Returns token, waits for participant confirm | loan initiation, deferral to 0% |
| `human_review` | Returns token, queued for sponsor approval | hardship distribution, QDRO, beneficiary update |

---

## Who Calls What — API Endpoints

| Endpoint | Calls | Notes |
|---|---|---|
| `POST /chat/fast` | `paap.execute()` | Haiku classifies intent first |
| `POST /transactions/confirm` | `paap.execute_confirmed()` | Non-disbursement only |
| `POST /transactions/disburse` | `paap.execute_confirmed()` | Loan / hardship disbursement |
| `POST /transactions/reallocate` | `paap.execute()` | Portal UI |
| `POST /transactions/change-deferral` | `paap.execute()` | Portal UI |
| `POST /paap/participants/*/loan` | `paap.execute()` via `_write()` | PAAP REST endpoint |
| CrewAI crew path | `ExecuteTransactionTool` | Kept for CrewAI only |

All portal writes go through PAAP. `ExecuteTransactionTool` is preserved for the CrewAI conversational path only.
