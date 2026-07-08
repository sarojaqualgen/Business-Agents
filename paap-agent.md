# PAAP Agent Spec — Participant Agent Protocol

## Overview

The PAAP Agent is the participant transaction execution layer of the agentic retirement services stack. It answers the question: **"What can this participant do — and executes it."**

It supports the full participant lifecycle from eligibility determination through final distribution: real-time eligibility checks, vesting lookups, deferral elections, investment reallocations, loan initiations, hardship distributions, RMD scheduling, rollover processing, and beneficiary updates. All writes are executed as deterministic, atomic API calls under ERISA-compliant audit frameworks.

---

## Responsibilities

- Expose read-only participant data surfaces: vesting percentage, account balance, loan headroom, projected RMD, Individual Benefit Statement, beneficiary designations
- Execute participant-directed transactions: deferral rate changes, fund reallocations, loan initiations, distribution requests, rollover-out requests, beneficiary updates
- Enforce plan-specific rules (sourced from PLAP) before allowing any transaction to proceed
- Maintain immutable audit logs on every API call — both reads and writes
- Respect blackout periods: block all transactional writes during active blackout windows
- Gate all write operations behind FAP authorization checks before execution

---

## Participant Data Model

### Identity & Eligibility
| Field | Type | Description |
|---|---|---|
| `participant_id` | string | Internal participant identifier |
| `plan_id` | string | Foreign key to PLAP |
| `ssn_hash` | string | Hashed SSN — never expose raw SSN to agents |
| `date_of_birth` | date | Used for age-gated rules (59½, 72/73/75 RMD) |
| `hire_date` | date | |
| `eligibility_date` | date | Date participant became eligible to participate |
| `employment_status` | enum | `active`, `terminated`, `retired`, `on_leave`, `military_leave` |
| `termination_date` | date | |
| `hours_of_service_ytd` | integer | For vesting calculations |
| `years_of_vesting_service` | float | Computed field |
| `break_in_service` | boolean | Whether participant has a qualifying break in service |
| `userra_military_leave` | boolean | Entitled to retroactive vesting and accrual |

### Account & Balance
| Field | Type | Description |
|---|---|---|
| `vested_balance` | decimal | Current vested account balance |
| `total_balance` | decimal | Total account balance including unvested |
| `vesting_percentage` | float | Current vesting percentage (0.0–1.0) |
| `employee_contributions_ytd` | decimal | |
| `employer_contributions_ytd` | decimal | |
| `investment_elections` | array | `[{ fund_id, allocation_pct }]` |

### Loans
| Field | Type | Description |
|---|---|---|
| `outstanding_loans` | array | `[{ loan_id, principal, balance, rate, maturity_date }]` |
| `max_additional_loan_amount` | decimal | Computed: min(50000 − highest balance last 12mo, 50% vested balance) |

### Distributions
| Field | Type | Description |
|---|---|---|
| `prior_hardship_distributions` | array | Dates and amounts — relevant for re-qualification |
| `rmd_required` | boolean | Whether participant has reached RMD mandatory start date |
| `rmd_amount_current_year` | decimal | Computed RMD for current plan year |
| `rmd_due_date` | date | |

---

## API Endpoints

### Read Operations (Roll out first)

#### `GET /participants/{participant_id}/summary`
Full benefit statement snapshot: balance, vesting, deferral rate, investment elections, outstanding loans, beneficiary.

#### `GET /participants/{participant_id}/vesting`
Current vesting percentage, years of service, schedule type, and next vesting milestone date.

#### `GET /participants/{participant_id}/loan-headroom`
Maximum additional loan amount under IRS cap and plan policy.

#### `GET /participants/{participant_id}/rmd`
Whether RMD is required, computed amount, due date, and calculation method used.

#### `GET /participants/{participant_id}/distribution-options`
Available distribution types given age, employment status, and plan rules (sourced from PLAP).

#### `GET /participants/{participant_id}/documents`
Individual Benefit Statement, vesting schedule, loan disclosures, distribution notices.

---

### Write Operations (After audit trail and FAP proven at scale)

All write operations require a valid FAP authorization token. All writes are logged immutably with: timestamp, agent identity, delegated authority type, action taken, inputs, outputs, and FAP token ID.

#### `POST /participants/{participant_id}/deferral`
Change pre-tax or Roth deferral percentage.

**Request:**
```json
{
  "deferral_type": "pre_tax | roth | after_tax",
  "deferral_pct": 0.06,
  "effective_payroll_date": "2026-07-01",
  "fap_token": "string"
}
```

**Validation:** Must not exceed IRS elective deferral limit for the plan year. Must be within plan's permitted deferral range.

---

#### `POST /participants/{participant_id}/investment-reallocation`
Reallocate future contributions and/or existing balance across plan's fund lineup.

**Request:**
```json
{
  "scope": "future_only | balance_only | both",
  "elections": [
    { "fund_id": "string", "allocation_pct": 0.60 },
    { "fund_id": "string", "allocation_pct": 0.40 }
  ],
  "fap_token": "string"
}
```

**Validation:** `allocation_pct` values must sum to 1.0. All `fund_id` values must exist in PLAP fund lineup. Blackout check required.

---

#### `POST /participants/{participant_id}/loan`
Initiate a new plan loan.

**Request:**
```json
{
  "amount": 10000,
  "repayment_years": 5,
  "purpose": "general | primary_residence",
  "fap_token": "string"
}
```

**Validation:** Amount ≤ `max_additional_loan_amount`. Repayment term ≤ plan maximum. Outstanding loan count check. Blackout check.

---

#### `POST /participants/{participant_id}/distributions/hardship`
Initiate a hardship distribution request.

**Request:**
```json
{
  "amount": 5000,
  "qualifying_expense_type": "medical | tuition | primary_home_purchase | prevent_eviction | funeral | casualty_loss | FEMA_disaster",
  "documentation_refs": ["string"],
  "fap_token": "string"
}
```

**Validation:** Participant must have an immediate and heavy financial need. Expense type must be in plan's approved list (sourced from PLAP). High-stakes — routes to human review queue before execution.

---

#### `POST /participants/{participant_id}/distributions/in-service`
Initiate an in-service distribution (age 59½ or plan-permitted age).

**Validation:** Participant must have reached plan's in-service distribution age. Taxable event — requires explicit acknowledgment in request payload. Routes to human review queue.

---

#### `POST /participants/{participant_id}/distributions/separation`
Initiate a separation-from-service distribution or direct rollover.

**Request:**
```json
{
  "distribution_type": "cash | direct_rollover_ira | direct_rollover_plan",
  "rollover_destination": { "institution": "string", "account_number_masked": "string" },
  "amount": "full | partial",
  "fap_token": "string"
}
```

**Validation:** Employment status must be `terminated` or `retired`. Direct rollover destination must be confirmed eligible. Routes to human review queue.

---

#### `POST /participants/{participant_id}/distributions/rmd`
Schedule or initiate a required minimum distribution.

**Validation:** `rmd_required` must be true. Amount must be ≥ computed `rmd_amount_current_year`. Due date compliance enforced.

---

#### `PUT /participants/{participant_id}/beneficiary`
Update primary and contingent beneficiary designations.

**Validation:** ERISA survivor benefit rules apply — if participant is married, QJSA spousal consent may be required. High-stakes — routes to human review queue.

---

#### `POST /participants/{participant_id}/qdro`
Initiate QDRO processing.

**Validation:** Required fields (participant name, alternate payee name, plan name, benefit amount or percentage, payment period) must all be present. Routes to plan administrator review queue. Never fully automated.

---

## Autonomy Levels

| Transaction | Autonomy Level | Rationale |
|---|---|---|
| Deferral rate increase | Full | Low liability, reversible |
| Rebalance to plan QDIA | Full | Low liability, plan-sanctioned default |
| Address update | Full | Administrative, no tax/legal consequence |
| Deferral rate decrease to 0% | Supervised | Opt-out — confirm intent |
| Loan initiation | Supervised | Reduces retirement savings |
| In-service distribution (59½+) | Human review | Taxable event, irreversible |
| Hardship distribution | Human review | Taxable + penalty risk, irreversibility |
| Pre-59½ distribution | Human review | 10% penalty unless exception applies |
| Beneficiary change | Human review | ERISA survivor benefit implications |
| QDRO processing | Human review | Legal order — never fully automated |
| Direct rollover out | Human review | Irreversible, high dollar amount |

---

## Edge Cases

The following edge cases must be tested against PLAP plan data before enabling agent writes at scale:

- **Break in service < 5 years**: Participant returns and platform must restore prior service credit
- **Military leave (USERRA)**: Participant entitled to retroactive vesting and benefit accrual upon return
- **Blackout period during recordkeeper transition**: All transactional writes blocked; PAAP must surface blackout notice to participant and agent
- **Loan default during leave of absence**: Suspend repayment per plan policy; do not trigger deemed distribution without confirmation

---

## Events (Outbound)

| Event | Trigger |
|---|---|
| `participant.contribution.deposited` | Payroll contribution posted |
| `participant.vesting.milestone` | Participant crosses a vesting breakpoint |
| `participant.loan.default` | Loan payment missed beyond cure period |
| `participant.rmd.due_soon` | 60 days before RMD due date |
| `participant.distribution.processed` | Any distribution completed |
| `participant.enrollment.completed` | Initial enrollment finalized |

---

## Audit & Observability

- Every API call (read and write) produces an immutable audit log entry
- Audit record includes: `timestamp`, `agent_id`, `participant_id`, `action`, `input_payload`, `output_payload`, `fap_token_id`, `plan_id`, `outcome`
- Plan sponsor and advisor dashboards must expose: agent-driven enrollment rates, deferral adequacy trends, loan default rates, hardship withdrawal frequency, rollover-in capture rate
- Leakage events (loan defaults, hardship withdrawals) must be surfaced as outcome metrics, not just engagement metrics

---

## Integration Points

| System | How PAAP Uses It |
|---|---|
| PLAP Agent | Queries plan capabilities, vesting rules, loan policy, hardship criteria before any transaction |
| FAP Agent | Submits proposed transaction for authorization check — FAP token required for all writes |
| Recordkeeping Core | Source of truth for participant balances, service records, payroll data |

---

## Non-Goals

- PAAP does not store or expose raw SSNs, full beneficiary PII, or marital status to third-party agents
- PAAP does not make investment recommendations — it executes participant-directed elections within the plan's lineup
- PAAP does not adjudicate QDRO orders — it initiates the processing queue and routes to human review
