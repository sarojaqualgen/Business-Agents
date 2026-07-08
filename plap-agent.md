# PLAP Agent Spec — Plan Agent Protocol

## Overview

The PLAP Agent is the plan discovery and data surface layer of the agentic retirement services stack. It answers the question: **"What does this plan allow?"**

It exposes structured, machine-readable plan data — plan type, fiduciary attributes, adoption agreement elections, fund lineup, operational parameters, and ERISA-governed policy rules — so that downstream agents (PAAP, FAP, and external planning agents) can reason about a specific plan without ambiguity.

---

## Responsibilities

- Serve as the authoritative source for plan-level data: plan type, employer matching formula, vesting schedule, normal retirement age, loan policy, hardship criteria, QDRO procedures, RMD calculation method, QJSA rules
- Generate and maintain PLAP-conformant data feeds from underlying plan records
- Support capability negotiation so agents can discover whether a plan endpoint supports a given transaction type (e.g., direct rollover, hardship distribution, QDRO processing)
- Enforce schema completeness at plan setup — reject incomplete plan configurations that would produce ambiguous agent responses
- Expose structured plan data across all participant touchpoints in real time

---

## Data Model

### Plan Identity
| Field | Type | Description |
|---|---|---|
| `plan_id` | string | Unique plan identifier |
| `plan_name` | string | Legal plan name |
| `plan_type` | enum | `401k`, `403b`, `457b`, `DB`, `ESOP`, `SEP`, `SIMPLE` |
| `safe_harbor` | boolean | Whether plan qualifies as safe harbor 401(k) |
| `erisa_plan_number` | string | 3-digit ERISA plan number |
| `effective_date` | date | Plan effective date |
| `plan_year_end` | string | Month/day of plan year end (e.g., `12/31`) |

### Employer Match
| Field | Type | Description |
|---|---|---|
| `match_formula` | object | Structured match tiers: `{ rate: 1.0, on_first_pct: 0.03 }, { rate: 0.5, on_next_pct: 0.02 }` |
| `match_true_up` | boolean | Whether annual true-up applies |
| `match_vesting_schedule_ref` | string | Reference to vesting schedule ID |

### Vesting Schedule
| Field | Type | Description |
|---|---|---|
| `vesting_type` | enum | `immediate`, `cliff`, `graduated` |
| `cliff_years` | integer | Years to 100% vesting under cliff schedule |
| `graduated_schedule` | array | `[{ year: 2, pct: 0.20 }, { year: 3, pct: 0.40 }, ...]` |
| `service_crediting_method` | enum | `hours_of_service`, `elapsed_time` |

### Loan Policy
| Field | Type | Description |
|---|---|---|
| `loans_permitted` | boolean | |
| `max_loan_amount` | integer | IRS cap: 50000 |
| `max_loan_pct_of_vested` | float | Typically 0.50 |
| `min_loan_amount` | integer | |
| `max_repayment_years` | integer | Typically 5 |
| `primary_residence_extension_years` | integer | Typically 15 |
| `outstanding_loans_permitted` | integer | Max concurrent loans |

### Hardship Distribution
| Field | Type | Description |
|---|---|---|
| `hardship_permitted` | boolean | |
| `hardship_standard` | enum | `safe_harbor`, `facts_and_circumstances` |
| `qualifying_expenses` | array | `medical`, `tuition`, `primary_home_purchase`, `prevent_eviction`, `funeral`, `casualty_loss`, `FEMA_disaster` |
| `six_month_contribution_suspension` | boolean | Pre-2019 rule still in force for this plan |

### Distribution Options
| Field | Type | Description |
|---|---|---|
| `in_service_age_59_5` | boolean | |
| `normal_retirement_age` | integer | Typically 65 |
| `early_retirement_age` | integer | |
| `rmd_start_rule` | enum | `age_73`, `age_75` (SECURE 2.0 transition) |
| `rmd_calculation_method` | enum | `uniform_lifetime`, `joint_life` |
| `qjsa_survivor_pct` | float | Typically 0.50 or 0.75 |
| `qjsa_waiver_requires_spousal_consent` | boolean | Always true under ERISA |

### Rollover & QDRO
| Field | Type | Description |
|---|---|---|
| `accepts_rollover_in` | boolean | |
| `rollover_in_sources` | array | `traditional_ira`, `employer_plan`, `roth_401k` |
| `direct_rollover_out_permitted` | boolean | |
| `qdro_procedures_url` | string | Machine-readable QDRO procedures document |
| `qdro_required_fields` | array | `participant_name`, `alternate_payee_name`, `plan_name`, `benefit_amount_or_pct`, `payment_period` |

---

## API Endpoints

### `GET /plans/{plan_id}`
Returns full structured plan record.

### `GET /plans/{plan_id}/capabilities`
Returns capability manifest — which transaction types the plan supports. Used for capability negotiation by downstream agents.

**Response schema:**
```json
{
  "plan_id": "string",
  "capabilities": {
    "loan_initiation": true,
    "hardship_distribution": true,
    "in_service_distribution": false,
    "direct_rollover_out": true,
    "qdro_processing": true,
    "rmd_scheduling": true
  }
}
```

### `GET /plans/{plan_id}/vesting`
Returns vesting schedule and service crediting rules.

### `GET /plans/{plan_id}/funds`
Returns investment lineup — fund name, ticker, expense ratio, asset class, whether it is the plan's QDIA.

### `GET /plans/{plan_id}/documents`
Returns links to SPD, plan document, adoption agreement, Annual Funding Notice, and blackout notices.

### `GET /plans/{plan_id}/blackout-status`
Returns current blackout period status and window dates. Agents must check this before executing any transactional write.

---

## Events (Outbound)

| Event | Trigger |
|---|---|
| `plan.amendment.published` | Formal plan amendment adopted |
| `plan.blackout.started` | Blackout period begins |
| `plan.blackout.ended` | Blackout period ends |
| `plan.annual_funding_notice.published` | AFN available |
| `plan.fund_lineup.changed` | Investment option added, removed, or substituted |

---

## ERISA Compliance Requirements

- All plan parameters must match formal plan document, not SPD narrative or portal copy
- Vesting schedule must encode both cliff and graduated variants with explicit year/percentage breakpoints
- Hardship criteria must be expressed as enumerated qualifying expense types, not free text
- RMD start date must reflect current SECURE 2.0 age thresholds (73 through 2032, 75 thereafter)
- QDRO required fields must be complete and legally sufficient per IRC §414(p)
- Schema completeness enforced at plan onboarding — incomplete plans block agent execution

---

## Integration Points

| Downstream | How PLAP is Used |
|---|---|
| PAAP Agent | Queries PLAP to validate whether a requested transaction type is permitted under the plan |
| FAP Agent | Reads PLAP plan attributes to evaluate fiduciary compliance of a proposed action |
| External planning agents | Consume PLAP capability manifest and fund lineup for participant advice |

---

## Non-Goals

- PLAP does not execute participant transactions (that is PAAP)
- PLAP does not enforce agent authorization (that is FAP)
- PLAP does not store participant-level data (SSN, balance, beneficiary) — only plan-level data
