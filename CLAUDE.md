# Aldergate — ERISA Agentic Retirement Services Stack
## CLAUDE.md — Context for Claude Code Sessions

---

## WHAT THIS PROJECT IS

An **ERISA-compliant 401(k) administration backend** called Aldergate. Three Python modules — named "agents" after their ERISA legal roles (plan agent, fiduciary agent, participant agent) — handle plan data, compliance enforcement, and participant execution respectively.

**They are NOT LLM agents.** They are deterministic Python code. No AI runs inside them.

The system processes participant actions — loan requests, deferral changes, distributions, rollovers — by routing every write through FAP (the compliance gate) before execution:
- PLAP reads plan rules from the database
- FAP runs 12 ERISA rules in pure Python — issues a signed JWT token if all pass
- PAAP executes writes only when handed a valid FAP token

**Interface architecture — two paths under consideration (decided in Phase 3):**

- **Path A — Portal + FastAPI:** A web portal calls structured REST endpoints. FastAPI routes requests to PLAP/FAP/PAAP. No LLM needed at runtime. Faster to build.
- **Path B — LLM + CrewAI Chatbot:** Participant types in plain English. Claude (LLM) interprets intent and calls PLAP/FAP/PAAP as CrewAI tools. Requires ANTHROPIC_API_KEY at runtime. More conversational.

Both paths keep the compliance engine (PLAP/FAP/PAAP) in pure Python — LLM never touches compliance decisions.

---

## THE THREE AGENTS

### PLAP — Plan Agent Protocol
- **Question it answers:** "What does this plan allow?"
- **Authoritative source for:** plan type, vesting schedule, loan policy, hardship criteria, fund lineup, blackout status
- **Does NOT hold:** participant data, balances, SSNs
- **Files:** `agents/plap/models.py`, `data/mock_plans.py`

### FAP — Fiduciary Agent Protocol
- **Question it answers:** "Is this authorized and ERISA-compliant?"
- **Core function:** Runs 12 ERISA rules in sequence. Issues a scoped JWT token if all pass. Any rule failure = denial, no token.
- **Files:** `agents/fap/compliance.py` (the 12 rules), `agents/fap/tokens.py`, `agents/fap/agent.py`
- **Key rule:** Fail fast — stops at first violation, never evaluates remaining rules

### PAAP — Participant Agent Protocol
- **Question it answers:** "What can this participant do — and executes it."
- **Only agent that touches participant account data**
- **Every write requires a valid FAP token** — no token, no execution
- **Files:** `agents/paap/models.py`, `data/mock_participants.py`

---

## CRITICAL RULES — DO NOT VIOLATE

1. **SSNs never appear anywhere** — only `ssn_hash` (SHA-256). If you see raw SSN in any model or response, it's a bug.
2. **Full account balance never goes to external agents** — only `loan_headroom` or `rmd_amount` as needed.
3. **Marital status never exposed** — FAP handles QJSA rules internally, returns boolean only.
4. **Date of birth never exposed externally** — FAP resolves age, returns boolean result.
5. **All 12 compliance rules must evaluate in order** — fail fast at first violation. Never skip or reorder.
6. **PAAP never executes writes without a valid FAP token** — no exceptions.
7. **Audit log is written for every FAP decision** — both approved AND denied. Never skip the audit write.
8. **Every rule must actually evaluate and fail correctly** — no stubs that always return approved.

---

## ARCHITECTURE DECISIONS

**Locked:**
- **[x] Database** — PostgreSQL ✅
- **[x] Plan onboarding** — Admin fills structured form (no PDF parsing) ✅
- **[x] Participant data source** — Recordkeeper SFTP/API feed (Phase 5) ✅
- **[x] Vector DB** — Not needed (plan rules are structured, not freeform) ✅
- **[x] Graph DB** — Not needed (QDRO fits relational joins) ✅

**Locked:**
- **[x] Interface** — Path B (LLM + CrewAI chatbot) ✅
  - Participant types plain English → Claude interprets → PLAP/FAP/PAAP execute
  - CrewAI chosen for structural role enforcement (compliance agent cannot call data tools)
  - Path A (FastAPI portal) will be added on top in Phase 4 as the web UI layer

---

## CREWAI AGENT ARCHITECTURE (Two Layers)

### Layer 1 — Domain Crews (who is logged in)
Each principal type gets its own crew with different tools and scope.

| Crew | Principal Type | Tools Available |
|---|---|---|
| ParticipantCrew | participant, participant_delegate | GetPlanRules, GetParticipantSummary, GetLoanHeadroom, RunComplianceCheck, ExecuteTransaction |
| SponsorCrew | plan_sponsor, plan_trustee | GetPlanRules, GetAuditLog, GetPendingReviews, ApproveRequest, DenyRequest, ManageBlackout |
| AdvisorCrew | investment_advisor | GetPlanRules, GetFundLineup, GetParticipantSummary, RunComplianceCheck, ExecuteTransaction |
| RecordkeeperPipeline | **NOT a crew** | Automated SFTP/API nightly sync → PostgreSQL (Phase 5) |

### Layer 2 — Workflow Agents (inside each crew)
Each crew contains the same three-agent execution pattern:
- **Intent Agent** — parses natural language, formats final response (no tools)
- **Data Agent** — fetches plan + participant data (PLAP/PAAP tools only)
- **Compliance Agent** — runs FAP via RunComplianceCheckTool only (never touches data tools)

### Plan Sponsor Full Duties
The plan sponsor has far more responsibilities than just plan onboarding:
1. **Approve/deny human_review queue** — hardship, QDRO, RMD, beneficiary, separation distributions
2. **Manage blackout periods** — mandatory 30-day notice per ERISA § 101(i)
3. **View FAP audit log** — ERISA § 107 requires 6-year retention; DOL can subpoena
4. **Nondiscrimination testing** — ADP/ACP testing oversight (annual)
5. **Forfeiture allocation** — allocate non-vested forfeited amounts each plan year
6. **Top-heavy testing** — IRC § 416 key employee ratio (annual)
7. **QDRO determination** — must qualify within 18 months (ERISA § 206(d))
8. **Mass notices** — safe harbor notice, blackout notice, 402(f) rollover notice, SAR
9. **Agent registry management** — issue/revoke agent credentials (add/remove from mock_agents.py)
10. **Plan amendments** — update vesting schedule, loan policy, fund lineup
11. **Form 5500 data** — annual filing preparation

### Recordkeeper (NOT a conversational crew)
- Recordkeeper = Fidelity, Vanguard, or Empower (third-party, holds the money)
- Sends nightly SFTP file drops with updated participant balances
- Aldergate parses and upserts into our PostgreSQL `participants` table
- This is an automated pipeline, not a ChatBot — no LLM involved
- Phase 5 deliverable

---

## CURRENT STATE (Phase 3 — Complete)

```
✅ Pydantic v2 models — PLAP, FAP, PAAP
✅ 12-rule FAP compliance engine (pure Python)
✅ JWT token issuance and single-use validation
✅ Mock data — 2 plans, 5 participants, 4 agents
✅ 86 pytest tests — every rule has pass and fail coverage
✅ Human review queue (data/review_queue.py)
✅ CrewAI tools — 8 tools wrapping PLAP/FAP/PAAP + admin
✅ CrewAI domain crews — ParticipantCrew, SponsorCrew, AdvisorCrew
✅ Crew router (crew/router.py) — routes by principal_type
✅ Interactive CrewAI CLI (demo/crew_cli.py)
✅ Supervised confirm/cancel flow (token held until participant confirms)
✅ Graceful API error handling (connection errors show clean message)
✅ SECURE 2.0 Roth catch-up (Rule 5, effective 2026)
✅ RMD notice enforcement (Rule 6)
✅ address_update action type (full autonomy)
✅ Document upload system — hardship + QDRO supporting docs
   ├── data/document_store.py — JSON-backed document records, persists to disk
   ├── data/sample_docs/ — 5 pre-filled demo documents (medical, eviction, tuition, funeral, QDRO)
   ├── crew/tools/document_tools.py — UploadDocumentTool, GetDocumentsTool, verify_document()
   ├── CLI: doc upload prompt after human_review queue (sample / file path / skip)
   ├── CLI: sponsor 'docs <entry_id>' command to view uploaded documents
   └── CLI: Approve BLOCKED for hardship/QDRO until verified docs on file
✅ LLM-based document verification — Claude Haiku (direct API, not CrewAI)
❌ Real database (Phase 2 schema done, Phase 6 wiring pending)
❌ FastAPI endpoints (Phase 4)
❌ Recordkeeper SFTP integration (Phase 5)
```

---

## TECH STACK

| Layer | Technology | Status |
|---|---|---|
| Agent orchestration | CrewAI 1.15.0 | ✅ Done (Phase 3) |
| LLM | Claude (claude-sonnet-4-6) via Anthropic API | ✅ Done (Phase 3) |
| Data models | Pydantic v2 | ✅ Done |
| Auth tokens | PyJWT (HS256) | ✅ Done |
| Human review queue | In-memory (data/review_queue.py) | ✅ Done |
| Database | PostgreSQL (alembic migrations) | Pending (Phase 2) |
| Token store | Python set → Redis | Pending |
| API | FastAPI | Pending (Phase 4) |
| Tests | pytest | ✅ Done |

---

## FILE STRUCTURE

```
project/
├── agents/
│   ├── plap/
│   │   ├── models.py        ← Pydantic models for plan config
│   │   └── tools.py         ← CrewAI tools (not built yet)
│   ├── fap/
│   │   ├── models.py        ← Auth request/response, audit log, RuleResult
│   │   ├── compliance.py    ← THE 12 ERISA RULES — core of the system
│   │   ├── tokens.py        ← JWT issuance and validation
│   │   └── agent.py         ← authorize() orchestrator
│   └── paap/
│       ├── models.py        ← Participant data models
│       └── tools.py         ← CrewAI tools (not built yet)
├── crew/
│   ├── tools/
│   │   ├── plap_tools.py    ← GetPlanRulesTool, GetFundLineupTool
│   │   ├── paap_tools.py    ← GetParticipantSummaryTool, GetLoanHeadroomTool, ExecuteTransactionTool
│   │   ├── fap_tools.py     ← RunComplianceCheckTool, GetAuditLogTool
│   │   └── admin_tools.py   ← GetPendingReviewsTool, ApproveRequestTool, DenyRequestTool, ManageBlackoutTool
│   ├── agents/
│   │   └── base.py          ← LLM init (claude-sonnet-4-6 via Anthropic API)
│   ├── crews/
│   │   ├── participant_crew.py  ← 3 agents, 6 tasks
│   │   ├── sponsor_crew.py      ← 3 agents, 4 tasks
│   │   └── advisor_crew.py      ← 3 agents, 5 tasks
│   └── router.py            ← routes to correct crew by principal_type
├── data/
│   ├── review_queue.py      ← In-memory human review queue (approved/denied by plan sponsor)
│   ├── document_store.py    ← Document records for hardship/QDRO (JSON-backed, wiped on CLI startup)
│   ├── mock_plans.py        ← 2 demo plans
│   ├── mock_participants.py ← 5 demo participants
│   ├── mock_agents.py       ← Agent registry
│   └── sample_docs/
│       ├── medical_bill.txt        ← Metro General Hospital, $1,865 due
│       ├── eviction_notice.txt     ← Eviction notice, $5,700 overdue rent
│       ├── tuition_invoice.txt     ← UIC M.S. program, $8,198 due
│       ├── funeral_invoice.txt     ← Lakeside Funeral Home, $5,001 balance
│       └── qdro_court_order.txt    ← Cook County Circuit Court, 50% vested balance
├── demo/
│   ├── loan_request_demo.py ← 3-scenario deterministic demo (no LLM)
│   ├── interactive_demo.py  ← Interactive compliance trace CLI (no LLM)
│   └── crew_cli.py          ← CrewAI multi-agent CLI (requires ANTHROPIC_API_KEY)
├── tests/
│   └── test_fap_compliance.py ← 86 tests
├── conftest.py              ← pytest sys.path fix
├── requirements.txt
├── .env.example
├── CLAUDE.md                ← This file
├── README.md
└── TESTING.md
```

---

## ERISA CONTRIBUTION LIMITS (2024) — HARDCODED IN compliance.py

These change every year when IRS publishes cost-of-living adjustments.
When limits change, update `agents/fap/compliance.py` lines with `LIMIT_402G`, `LIMIT_414V_50`, etc.

| Limit | 2024 Value | Variable in code |
|---|---|---|
| Employee elective deferral | $23,000 | `LIMIT_402G` |
| Catch-up age 50+ | $7,500 | `LIMIT_414V_50` |
| Catch-up ages 60-63 (2025+) | $10,000 | `LIMIT_414V_60_63` |
| Total annual additions | $69,000 | `LIMIT_415C` |
| Compensation cap | $345,000 | `LIMIT_COMP_CAP` |

---

## PYDANTIC V2 — IMPORTANT

This project uses Pydantic v2 syntax. Do NOT use v1 patterns:
- Use `model_validator` not `@validator`
- Use `field_validator` not `@validator`
- Use `model_config = ConfigDict(...)` not `class Config:`

---

## WHAT THE .env FILE CONTROLS

```
ANTHROPIC_API_KEY   — Claude API key. NOT used yet. Required for Phase 3 (CrewAI wiring).
FAP_JWT_SECRET      — Signs all FAP tokens. Falls back to insecure default in dev.
                      MUST be changed for any non-local deployment.
```

Copy `.env.example` to `.env` and fill in values before running Phase 3.

---

## RUNNING THE PROJECT

```bash
# Install dependencies
pip install -r requirements.txt

# Run the loan request demo (no API key needed)
python demo/loan_request_demo.py

# Run all tests (no API key needed)
pytest tests/ -v
```

---

## KEY ERISA CONCEPTS TO KNOW

**Blackout period** — A temporary freeze on all account writes, required during recordkeeper transitions. ERISA § 101(i) requires 30-day advance notice. All writes blocked during blackout; reads still permitted.

**Vesting** — Employee's own contributions are always 100% vested immediately. Employer match follows a schedule (cliff: 100% at 3 years, or graduated: 20%/yr over 6 years). A participant can only take unvested employer match if they're vested.

**IRC § 72(p) loan cap** — Max loan is the LESSER of ($50,000 minus highest loan balance in last 12 months) OR (50% of vested balance). Both limits apply simultaneously.

**Autonomy levels** — FAP assigns one of three levels to every approved transaction:
- `full` — execute immediately (deferral increase, rebalance to QDIA)
- `supervised` — surface confirmation to participant first (loan initiation, deferral to 0%)
- `human_review` — queue for human admin (hardship, QDRO, beneficiary change, rollover out)
  - For `hardship_distribution` and `qdro`: participant must upload and verify supporting documents BEFORE sponsor can approve
  - Sponsor Approve is blocked until at least one verified document is on file for that queue entry
  - Other human_review actions (beneficiary, separation, rmd) have no document requirement in current demo

**Audit retention** — Every FAP decision (approved or denied) must be retained for minimum 6 years per ERISA § 107.
