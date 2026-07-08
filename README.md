# Aldergate — ERISA Agentic Retirement Services Stack

An ERISA-compliant 401(k) administration backend with a multi-agent AI interface.
Participants type plain English. Three deterministic Python modules enforce compliance — no AI makes a compliance decision.

---

## The Core Rule

Every write goes through FAP. FAP runs 12 ERISA rules in pure Python. If all 12 pass, FAP issues a signed JWT token. PAAP will not execute a single write without that token. The LLM interprets intent and calls PLAP/FAP/PAAP as tools — it never decides whether a transaction is legal.

---

## Architecture

```
Participant types in English
        ↓
   [IntentAgent]      — LLM: parses natural language
        ↓
   [DataAgent]        — LLM: fetches plan rules (PLAP) + participant data (PAAP)
        ↓
   [ComplianceAgent]  — LLM calls FAP: 12 ERISA rules run in pure Python
        ↓
   [DataAgent]        — LLM: executes transaction or queues for sponsor
        ↓
   [IntentAgent]      — LLM: writes plain-English response
```

**PLAP, FAP, and PAAP are not LLM agents.** They are deterministic Python. The name "agent" comes from ERISA law — "plan agent" and "fiduciary agent" are legal roles in federal retirement code.

---

## The Three Modules

| Module | Role | Never does |
|---|---|---|
| PLAP | "What does this plan allow?" | Hold participant data |
| FAP | "Is this ERISA-compliant?" → issues JWT | Execute transactions |
| PAAP | "Execute it — only with a token" | Run without a FAP token |

---

## The 12 FAP Compliance Rules

Every transaction is checked against all 12 rules in order. Fail any one → denied immediately. The rest do not run.

| Rule | What it checks | ERISA / IRC cite |
|---|---|---|
| 1 | Is this agent registered and in scope? | ERISA §404 |
| 2 | Is the plan in an active blackout? | ERISA §101(i) |
| 3 | Has the participant met eligibility requirements? | ERISA §202 / IRC §410(a) |
| 4 | Is the participant vested in employer contributions? | ERISA §203 / IRC §411 |
| 5 | Does the deferral stay within IRS annual limits? | IRC §§402(g), 414(v), 415(c) |
| 6 | Do plan-specific rules allow this transaction? | IRC §72(p) / §401(k) |
| 7 | Does the early withdrawal penalty apply? | IRC §72(t) |
| 8 | Is the participant pledging their benefit as collateral? | ERISA §206(d) |
| 9 | Is this a prohibited party-in-interest transaction? | ERISA §406 / IRC §4975 |
| 10 | Does this require prudent expert / human review flag? | ERISA §404 |
| 11 | Is there an outstanding RMD that would be missed? | IRC §401(a)(9) |
| 12 | What autonomy level applies? (full / supervised / human_review) | — |

---

## Autonomy Levels

| Level | Meaning | Examples |
|---|---|---|
| `full` | Execute immediately | Deferral increase, rebalance to QDIA, address update |
| `supervised` | Participant must type `confirm` | Loan initiation, deferral to 0% |
| `human_review` | Plan sponsor must approve | Hardship, QDRO, separation distribution, RMD |

---

## Data Privacy Rules

| Data | Rule |
|---|---|
| SSN | Never stored raw — SHA-256 hash only |
| Full account balance | Never exposed — only `loan_headroom` or `rmd_amount` |
| Date of birth | Never exposed — FAP resolves age internally, returns boolean |
| Marital status | Never exposed — FAP enforces QJSA internally, returns boolean |

---

## Getting Started

### Prerequisites

- Python 3.11+
- An [Anthropic API key](https://console.anthropic.com/)

### Clone and run

```bash
# 1. Clone the repo
git clone https://github.com/sarojaqualgen/Business-Agents.git
cd Business-Agents

# 2. Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate        # Mac / Linux
# .venv\Scripts\activate         # Windows

# 3. Install dependencies
pip install -r requirements.txt

# 4. Set up environment variables
cp .env.example .env
```

Open `.env` and fill in:

```
ANTHROPIC_API_KEY=sk-ant-...     # your Anthropic API key
FAP_JWT_SECRET=change-me-in-prod # any long random string for dev
```

### Run the CLI

```bash
python demo/crew_cli.py
```

Three roles: Participant (loans · deferrals · investments · distributions), Plan Sponsor (approve queue · blackouts · audit log), Investment Advisor (reallocation + deferral recommendations).

See [CLI_GUIDE.md](CLI_GUIDE.md) for a full explanation of every action and option.

## Running Tests (no API key needed)

```bash
pytest tests/ -v
```

87 tests. All pass. Every FAP rule has both a pass case and a fail case. No stubs.

---

## Phase Status

| Phase | Status | Description |
|---|---|---|
| 1 — Core Engine | Done | Pydantic v2 models, 12-rule FAP engine, mock data, tests, demo |
| 2 — Data Layer | Done | PostgreSQL schema, `data/db.py`, Alembic migrations |
| 3 — CrewAI + LLM | Done | CrewAI crews, Claude claude-sonnet-4-6, interactive CLI |
| 4 — FastAPI API | Pending | REST endpoints (web portal calls these) |
| 5 — Recordkeeper | Pending | SFTP/API nightly sync from Fidelity/Vanguard/Empower |
| 6 — Production | Pending | Redis tokens, PII encryption, DOL compliance audit |

---

## Key Files

| File | Purpose |
|---|---|
| `agents/fap/compliance.py` | The 12 ERISA rules — core of the system |
| `agents/fap/tokens.py` | JWT issuance and single-use validation |
| `agents/plap/models.py` | Plan configuration data models |
| `agents/paap/models.py` | Participant account data models |
| `crew/crews/participant_crew.py` | ParticipantCrew — 3 agents, 6 tasks |
| `crew/crews/sponsor_crew.py` | SponsorCrew — 3 agents, 4 tasks |
| `crew/router.py` | Routes to the correct crew by principal_type |
| `demo/crew_cli.py` | Interactive multi-agent CLI |
| `data/plans.py` | Plan data layer — reads from PostgreSQL |
| `data/participants.py` | Participant data layer — reads from PostgreSQL |
| `tests/test_fap_compliance.py` | 87 tests — every rule, pass + fail |

---

## Documentation

| File | What it covers |
|---|---|
| [CLI_GUIDE.md](CLI_GUIDE.md) | Every CLI option, all 10 actions, confirm/cancel flow, error messages |
| [DEMO_GUIDE.md](DEMO_GUIDE.md) | 8 scripted demo scenarios for presentations |
| [TESTING.md](TESTING.md) | Test architecture, rule-by-rule breakdown, mock data reference |
| [WORKFLOW2.md](WORKFLOW2.md) | Full architecture spec — agents, tasks, tools, data flow |
| [CLAUDE.md](CLAUDE.md) | Project context and critical rules for Claude Code sessions |
