# FAP Agent Spec — Fiduciary Agent Protocol

## Overview

The FAP Agent is the authorization and compliance enforcement layer of the agentic retirement services stack. It answers the question: **"Is this agent authorized to do it — and is it ERISA-compliant?"**

FAP is PLAP- and PAAP-compatible. It sits between any external or internal agent and the PAAP execution layer, ensuring that every transaction carries a verifiable digital analog to the ERISA Section 404 prudent expert and exclusive benefit standards before it executes. No PAAP write completes without a valid FAP token.

---

## ERISA Master Reference

**All compliance rules in this spec are derived from and must be kept in sync with:**

> [`specs/ERISA_401k_Rules_Consolidated.docx`](./ERISA_401k_Rules_Consolidated.docx)
> *ERISA Rules for 401(k) Retirement Plans — Consolidated Reference Guide*
> Sources: U.S. Department of Labor (EBSA) | GovInfo COMPS-896 | PensionResource.website
> As of June 2026

When a rule in this spec conflicts with the master reference document, the master reference wins. When the master reference is updated (e.g., for new IRS cost-of-living adjustments, SECURE Act amendments, or DOL regulatory changes), the compliance engine rules below must be updated to match before any deployment.

Each rule below cites the controlling ERISA section or IRC provision from the master reference. Citations follow the format: **[ERISA §X / IRC §Y — Master Ref §Z]**.

---

## Core Mandate

FAP enforces three pillars on every proposed transaction:

1. **Identity & Delegation** — Verify exactly who an agent represents (participant, plan sponsor, authorized investment advisor, plan trustee) and what ERISA-governed actions they are permitted to execute
2. **Zero-Trust Security** — Issue temporary, scoped tokens; minimize exposure of participant PII to third-party models
3. **Regulatory Compliance Enforcement** — Enforce plan-specific ERISA rules as machine-executable constraints before the transaction reaches PAAP

---

## Responsibilities

- Authenticate agent identity and resolve delegated authority scope
- Issue time-limited, transaction-scoped authorization tokens to approved agents
- Check each proposed transaction against plan rules sourced from PLAP (loan cap, hardship eligibility, QJSA waiver requirements, blackout status, RMD mandatory start dates)
- Block any transaction that would expose the plan fiduciary to compliance liability, even if the participant has explicitly requested it
- Never expose raw SSN, full account balance, beneficiary PII, or marital status to third-party AI models — surface only the minimum necessary fields
- Produce an immutable compliance audit record for every authorization decision (approved or denied)
- Surface denial reasons in structured, machine-readable format so PAAP and the requesting agent can respond appropriately

---

## Principal Types

FAP must resolve one of the following principal types for every agent request. The principal type determines the permission scope.

| Principal Type | Description | Permitted Actions |
|---|---|---|
| `participant` | The plan participant acting on their own behalf | Full self-directed transaction scope within plan rules |
| `plan_sponsor` | The employer or plan administrator | Plan-level actions: fund lineup changes, plan amendments, contribution submissions |
| `investment_advisor` | RIA or broker-dealer with participant or plan-level advisory agreement | Read-only plus reallocation within advisory mandate; no distributions |
| `plan_trustee` | Named trustee under the trust agreement | Trust-level asset and compliance actions |
| `participant_delegate` | Third party with explicit written participant delegation on file | Constrained to the specific actions listed in the delegation agreement |

---

## Authorization Flow

```
Agent → FAP: propose_transaction(agent_id, principal_type, participant_id, action, payload)
FAP → Identity Store: verify agent_id and delegation chain
FAP → PLAP: fetch plan rules and capabilities for participant's plan
FAP → Compliance Engine: evaluate action against ERISA master reference rules
FAP → Risk Engine: evaluate transaction autonomy level
FAP → PAAP (if approved): issue scoped token
FAP → Audit Log: record decision with ERISA citation
```

---

## API Endpoints

### `POST /authorize`
Core authorization endpoint. Called by PAAP before executing any write.

**Request:**
```json
{
  "agent_id": "string",
  "principal_type": "participant | plan_sponsor | investment_advisor | plan_trustee | participant_delegate",
  "participant_id": "string",
  "plan_id": "string",
  "action": "deferral_change | investment_reallocation | loan_initiation | hardship_distribution | in_service_distribution | separation_distribution | rmd | beneficiary_update | qdro",
  "payload": { }
}
```

**Response (approved):**
```json
{
  "authorized": true,
  "token": "string",
  "token_expires_at": "ISO8601",
  "autonomy_level": "full | supervised | human_review",
  "conditions": [ ],
  "erisa_citations": ["string"],
  "audit_id": "string"
}
```

**Response (denied):**
```json
{
  "authorized": false,
  "denial_reason": "string",
  "denial_code": "LOAN_CAP_EXCEEDED | BLACKOUT_ACTIVE | INSUFFICIENT_DELEGATION | HARDSHIP_CRITERIA_NOT_MET | QJSA_CONSENT_REQUIRED | RMD_NOT_YET_REQUIRED | EARLY_WITHDRAWAL_PENALTY_APPLIES | ANTI_ALIENATION_VIOLATION | PROHIBITED_TRANSACTION | ...",
  "erisa_citation": "string",
  "master_ref_section": "string",
  "audit_id": "string"
}
```

`erisa_citation` and `master_ref_section` in denial responses allow the requesting agent and human reviewers to locate the exact controlling rule in the master reference document.

---

### `GET /agents/{agent_id}/scope`
Returns the full authorized action scope for a given agent and principal type. Used by external agents to self-limit their requests before calling PAAP.

---

### `POST /agents/register`
Register a new agent with its identity, principal type, and delegation evidence.

**Request:**
```json
{
  "agent_id": "string",
  "agent_name": "string",
  "principal_type": "string",
  "delegation_document_ref": "string",
  "allowed_plan_ids": ["string"],
  "allowed_actions": ["string"],
  "token_max_ttl_seconds": 300
}
```

---

### `POST /tokens/revoke`
Immediately revoke an active authorization token. Used when delegation is withdrawn or a breach is suspected.

---

### `GET /audit/{audit_id}`
Retrieve a specific authorization decision record. Used by plan fiduciaries, compliance officers, and DOL audit processes.

---

## Compliance Engine Rules

FAP evaluates the following rule categories in order. A failure at any layer blocks the transaction. Every rule below cites its controlling provision in the ERISA master reference document.

### 1. Delegation Validity

- Agent must be registered and have an active, non-revoked delegation record
- Principal type must match the delegation agreement on file
- Delegation must explicitly cover the requested `action`
- **[ERISA § 404 — Master Ref §6.1, §6.2]**: Only persons exercising discretionary authority over plan management or administration qualify as fiduciaries. An agent acting on a participant's behalf must carry verifiable delegated authority.

### 2. Blackout Period Check

- Sourced from PLAP `GET /plans/{plan_id}/blackout-status`
- Any transactional write during an active blackout is blocked with `BLACKOUT_ACTIVE`
- Read-only operations are permitted during blackouts
- **[ERISA § 101(i) — Master Ref §7.7]**: Plan must provide at least 30 days' advance notice before a blackout period. FAP must enforce a write block for the full duration of any active blackout.

### 3. Participation and Eligibility Checks

- **[ERISA § 202 / IRC § 410(a) — Master Ref §2.2]**: A participant must have met the plan's age (max 21) and service (max 1 year / 1,000 hours) requirements before any contribution or distribution transaction is permitted.
- **[Master Ref §2.3]**: A year of service = 12-month period with ≥ 1,000 hours of service. FAP must verify eligibility date from PLAP before approving enrollment or contribution transactions.
- **[Master Ref §2.4]**: Entry date may be delayed to the earlier of the first plan year start after meeting requirements or 6 months after meeting requirements — FAP must not approve participant transactions before the effective eligibility date.
- **[Master Ref §2.5 — Break-in-Service]**: Prior service is disregarded only if the participant has ≥ 5 consecutive one-year breaks AND was 0% vested at break. FAP must verify break-in-service status from PLAP before blocking or restoring service credit.

### 4. Vesting Enforcement

- **[ERISA § 203 / IRC § 411 — Master Ref §3.1]**: Employee elective deferrals are always 100% immediately vested. FAP must never block a participant from accessing their own deferral contributions on vesting grounds.
- **[Master Ref §3.2 — Cliff Vesting]**: Employer contributions under cliff vesting: 0% vested before 3 years of service, 100% at exactly 3 years.
- **[Master Ref §3.2 — Graded Vesting]**: Employer contributions under graded vesting: 20% at year 2, 40% at year 3, 60% at year 4, 80% at year 5, 100% at year 6.
- **[Master Ref §3.2 — Safe Harbor]**: Safe harbor 401(k) employer contributions are immediately 100% vested.
- **[Master Ref §3.4]**: Service before a break in service counts for vesting after return, provided the break was fewer than 5 consecutive one-year breaks, or the participant was vested at the time of the break.
- FAP must source vesting schedule type and current vesting percentage from PLAP and enforce these thresholds when authorizing distribution transactions against employer contribution balances.

### 5. Contribution Limit Enforcement

- **[IRC § 402(g)(1) — Master Ref §4.2]**: Employee elective deferral limit: $23,000 (2024). FAP must block deferral elections that would cause the participant to exceed the annual 402(g) limit.
- **[IRC § 414(v) — Master Ref §4.2]**: Catch-up contribution limit for age 50+: $7,500 (2024). For ages 60–63 starting 2025: the greater of $10,000 or 150% of the regular catch-up limit (SECURE 2.0).
- **[IRC § 415(c) — Master Ref §4.2]**: Total annual additions limit: $69,000 (2024), or 100% of compensation if less.
- **[IRC § 401(a)(17) — Master Ref §4.2]**: Compensation cap for contribution calculations: $345,000 (2024).
- **[Master Ref §4.2 — SECURE 2.0]**: Catch-up contributions for participants earning over $145,000 must be Roth (effective 2026). FAP must enforce Roth catch-up routing for high-earning participants.

### 6. Plan Rule Enforcement (sourced from PLAP)

| Action | Rules Enforced | Master Ref Citation |
|---|---|---|
| `loan_initiation` | Amount ≤ lesser of $50,000 (reduced by highest outstanding loan balance in prior 12 months) or 50% of vested balance; repayment at least quarterly; max 5-year term (longer for primary residence); commercially reasonable interest rate | IRC § 72(p) — Master Ref §5.5 |
| `hardship_distribution` | Expense type must be in plan's approved safe harbor list; immediate and heavy financial need standard; 6-month deferral suspension rule is eliminated (post-2018) — contributions may continue immediately | IRC § 401(k)(2)(B)(i)(IV) — Master Ref §5.4 |
| `in_service_distribution` | Participant must have reached plan's in-service distribution age (age 59½ minimum) | IRC § 401(a) — Master Ref §5.1 |
| `separation_distribution` | Employment status must be `terminated` or `retired`; rollover destination confirmed eligible; 402(f) rollover notice must be provided 30–180 days before distribution | IRC § 402 — Master Ref §5.1, §7.7 |
| `rmd` | `rmd_required = true`; amount ≥ computed RMD (account balance ÷ IRS Uniform Lifetime Table factor); RMD age is 73 for those born 1951–1959, 75 for those born after 1959 (SECURE 2.0); Roth 401(k) exempt from RMDs during owner's lifetime (effective 2024) | IRC § 401(a)(9) — Master Ref §5.2 |
| `beneficiary_update` | If married: surviving spouse must receive 100% of vested balance unless spouse consents in writing, witnessed by plan representative or notary public; QJSA/QPSA notice required 30–180 days before annuity start date | ERISA § 205 / IRC § 401(a)(11) — Master Ref §5.7, §7.7 |
| `qdro` | Required fields present: participant name, alternate payee name, plan name, benefit amount or percentage, payment period; plan must determine qualification within 18 months; alternate payee share must be segregated during determination; distributions to alternate payee are not subject to 10% early withdrawal penalty | ERISA § 206(d) / IRC § 414(p) — Master Ref §5.6 |

### 7. Early Withdrawal Penalty Check

- **[IRC § 72(t) — Master Ref §5.3]**: Distributions before age 59½ are subject to a 10% early withdrawal penalty in addition to ordinary income tax. FAP must flag and require human review for any pre-59½ distribution.
- Penalty exceptions that FAP must evaluate before blocking:
  - Separation from service at age 55 or older (age 50 for public safety employees)
  - Disability (IRC § 72(m)(7))
  - Death (distributions to beneficiaries)
  - Substantially equal periodic payments (SEPP / 72(t) election)
  - Qualified domestic relations orders (QDROs)
  - Medical expenses exceeding 7.5% of AGI
  - Qualified reservist distributions
  - Qualified birth or adoption distributions (up to $5,000 per event)
  - Emergency personal expense distributions up to $1,000/year (SECURE 2.0, 2024)
  - Domestic abuse victim distributions (SECURE 2.0, 2024)
  - Terminal illness distributions (SECURE 2.0, 2024)

### 8. Anti-Alienation Check

- **[ERISA § 206(d) / IRC § 401(a)(13) — Master Ref §8.2]**: Plan benefits may not be assigned or alienated. FAP must block any transaction that pledges a participant's 401(k) account as collateral, except for:
  - Permissible plan loans (IRC § 72(p))
  - Qualified domestic relations orders (QDROs)
  - Federal tax levies
  - Offsets for defaulted plan loans

### 9. Prohibited Transaction Check

- **[ERISA § 406 / IRC § 4975 — Master Ref §6.3]**: FAP must block any transaction that constitutes a prohibited transaction between the plan and a party in interest: sale/exchange of property, lending of money, furnishing of goods or services, transfer of plan assets for the benefit of a party in interest, or acquisition of employer securities exceeding 10% of plan assets.
- Statutory exemptions FAP must recognize before blocking:
  - Participant loans meeting IRC § 72(p) requirements
  - Payment of reasonable plan expenses
  - Purchase or sale of qualifying employer securities at fair market value
- **[Master Ref §6.4 — PTE 2020-02]**: Investment advice exemption applies to rollover recommendations and ongoing advice by investment advisors — FAP must verify PTE applicability before blocking advisor-initiated reallocation transactions.

### 10. ERISA Section 404 Prudent Expert and Loyalty Check

- **[ERISA § 404 — Master Ref §6.2]**: For high-stakes irreversible transactions (distributions, QDROs, beneficiary changes), FAP must confirm:
  - Transaction is solely in the interest of the participant and beneficiaries (Duty of Loyalty)
  - Transaction is consistent with the care of a prudent person familiar with retirement plan matters (Duty of Prudence)
  - Transaction follows the plan document (Duty to Follow Plan Documents)
  - If the agent is an investment advisor, the action is within their advisory mandate and ERISA § 404(a)(5) fee disclosure obligations have been met

### 11. RMD Failure Prevention

- **[IRC § 401(a)(9) — Master Ref §5.2]**: Failure to distribute the required RMD amount triggers a 25% excise tax on the shortfall (reduced from 50% by SECURE 2.0), reducible to 10% if corrected timely. FAP must block any distribution that would result in an RMD shortfall for the current plan year.
- FAP must issue a `participant.rmd.due_soon` event (via PAAP) by January 31 of the year the RMD is due. **[Master Ref §7.7 — RMD Notices]**

### 12. Autonomy Level Assignment

After all compliance checks pass, FAP assigns an autonomy level to the approved token:

| Autonomy Level | Definition | Examples | Master Ref Basis |
|---|---|---|---|
| `full` | Agent may execute immediately without additional human confirmation | Deferral increase, rebalance to QDIA, address update | Low ERISA liability; reversible |
| `supervised` | Agent may proceed but must surface confirmation to participant before final execution | Deferral decrease to 0%, loan initiation | IRC § 72(p) loan requirements; reduces retirement savings |
| `human_review` | Transaction queued for plan administrator or advisor review before execution | Hardship distribution, in-service distribution, beneficiary change, QDRO, rollover out | ERISA §§ 203, 205, 206(d); IRC §§ 72(t), 401(a)(9), 414(p) |

---

## Safe Harbor Hardship Expense Types

The following expense types are automatically deemed to meet the "immediate and heavy financial need" standard under the safe harbor. FAP must reject hardship distribution requests citing any expense type not on this list unless the plan uses a facts-and-circumstances standard (sourced from PLAP).

**[IRC § 401(k)(2)(B)(i)(IV) / Reg. § 1.401(k)-1(d)(3) — Master Ref §5.4]**

1. Medical expenses for participant, spouse, dependents, or primary beneficiary
2. Purchase (not mortgage payments) of principal residence
3. Tuition and related educational expenses (next 12 months) for participant, spouse, children, or dependents
4. Payments to prevent eviction from or foreclosure on principal residence
5. Burial or funeral expenses for parent, spouse, children, or dependents
6. Repair of principal residence damage qualifying as a casualty deductible loss
7. Expenses due to a federally declared disaster

Post-2018 rule: The 6-month deferral suspension after a hardship withdrawal is eliminated. FAP must not block contribution elections made immediately after a hardship withdrawal.

---

## Contribution Limits Quick Reference

FAP's compliance engine must use the values from the master reference document as the authoritative source. These limits are subject to annual IRS cost-of-living adjustments — update the compliance engine each year when the master reference is refreshed.

**[IRC §§ 402(g), 414(v), 415(c), 401(a)(17) — Master Ref §4.2, §11]**

| Limit | 2024 Value | IRC Basis |
|---|---|---|
| Employee elective deferral (402(g)) | $23,000 | IRC § 402(g)(1) |
| Catch-up contribution age 50+ | $7,500 additional | IRC § 414(v) |
| Catch-up contribution ages 60–63 (2025+) | Greater of $10,000 or 150% of regular catch-up | SECURE 2.0 |
| Total annual additions (415(c)) | $69,000 (or 100% of compensation) | IRC § 415(c) |
| Compensation cap | $345,000 | IRC § 401(a)(17) |
| HCE threshold | $155,000 | IRC § 414(q) |

---

## Vesting Schedule Quick Reference

**[ERISA § 203 / IRC § 411 — Master Ref §3.2, §11]**

| Schedule Type | Rule |
|---|---|
| Employee deferrals | Immediately 100% vested — always |
| Cliff vesting (employer match) | 0% before 3 years; 100% at exactly 3 years |
| Graded vesting (employer match) | 20% yr 2 → 40% yr 3 → 60% yr 4 → 80% yr 5 → 100% yr 6 |
| Safe harbor contributions | Immediately 100% vested |
| SIMPLE 401(k) | Immediately 100% vested |

---

## Token Design

- Tokens are JWT-based, signed with plan-level keys
- Scoped to: `agent_id`, `participant_id`, `plan_id`, `action`, `payload_hash`
- Default TTL: 300 seconds (5 minutes)
- Single-use for write operations — a token consumed by PAAP cannot be reused
- `payload_hash` binds the token to the exact transaction payload; modified payloads produce token validation failure

---

## PII Minimization

FAP enforces the following constraints on what participant data third-party agents may receive. Exposure of PII beyond these limits triggers DOL cybersecurity notification obligations.

**[DOL Cybersecurity Guidance — Master Ref §6.5 (bonding), §7 (disclosure)]**

| Data Field | External Agent Access |
|---|---|
| SSN | Never — only hashed identifier |
| Full account balance | Never — loan headroom and RMD amount only, as needed for transaction |
| Beneficiary name/address | Never exposed to external agents |
| Marital status | Never — QJSA rules enforced by FAP internally |
| Date of birth | Never — age eligibility resolved by FAP; agent receives boolean result |

---

## DOL Cybersecurity Compliance

FAP must meet DOL cybersecurity guidance for ERISA-covered plans:

- Annual third-party security audits
- Penetration testing of all agent-facing endpoints
- Multi-factor authentication for any agent with write scope
- Participant notification required for any breach involving online account information
- **[ERISA § 107 / 29 U.S.C. § 1027 — Master Ref §9]**: Immutable audit logs retained for minimum 6 years per ERISA record retention requirements

---

## Notice and Disclosure Enforcement

FAP must check that required participant notices have been issued before authorizing certain transactions. Sourced from PLAP document feeds.

**[ERISA §§ 101–111 — Master Ref §7.7]**

| Notice | Timing Requirement | Blocks If Missing |
|---|---|---|
| 402(f) Rollover Notice | 30–180 days before distribution | `separation_distribution`, `rmd` (first-time) |
| QJSA/QPSA Notice | 30–180 days before annuity start date | `beneficiary_update` if annuity plan |
| Blackout Notice | At least 30 days before blackout | All writes during blackout |
| RMD Notice | By January 31 of RMD year | `rmd` if not yet issued |
| Safe Harbor Notice | At least 30 days before plan year start | New-year contribution elections on safe harbor plans |

---

## Audit Log Schema

Every authorization decision — approved or denied — produces an immutable record:

| Field | Type |
|---|---|
| `audit_id` | UUID |
| `timestamp` | ISO 8601 |
| `agent_id` | string |
| `principal_type` | enum |
| `participant_id` | string |
| `plan_id` | string |
| `action` | string |
| `authorized` | boolean |
| `denial_code` | string (null if approved) |
| `erisa_citation` | string — controlling ERISA/IRC section from master reference |
| `master_ref_section` | string — e.g., "§5.5", "§6.2" |
| `autonomy_level` | enum (null if denied) |
| `token_id` | string (null if denied) |
| `plap_snapshot_version` | string (version of plan rules at decision time) |
| `erisa_master_ref_version` | string — date-stamped version of master reference doc used |
| `fap_rule_engine_version` | string |

---

## Events (Outbound)

| Event | Trigger |
|---|---|
| `fap.authorization.denied` | Any blocked transaction |
| `fap.token.issued` | Authorization approved |
| `fap.token.revoked` | Manual or automated revocation |
| `fap.agent.registered` | New agent registration |
| `fap.compliance.alert` | Pattern of repeated denials suggesting misconfigured or malicious agent |
| `fap.erisa_ref.update_required` | Master reference document version has changed — compliance engine rules need review |

---

## Integration Points

| System | How FAP Uses It |
|---|---|
| ERISA Master Reference | [`specs/ERISA_401k_Rules_Consolidated.docx`](./ERISA_401k_Rules_Consolidated.docx) — source of truth for all compliance rule thresholds and citations |
| PLAP Agent | Fetches plan-specific rules and blackout status for per-plan compliance checks |
| PAAP Agent | Receives FAP token; validates token before executing any write |
| Identity Store | Resolves agent registration, delegation scope, and principal type |
| Plan Sponsor Dashboard | Surfaces compliance alerts and authorization audit trail |

---

## Keeping the Compliance Engine in Sync with the Master Reference

The ERISA master reference document (`ERISA_401k_Rules_Consolidated.docx`) must be reviewed and this spec updated whenever:

1. **IRS announces annual cost-of-living adjustments** — contribution limits (§4.2), compensation cap (§4.2), HCE threshold (§4.2) change each year
2. **New legislation passes** — SECURE, SECURE 2.0, or future acts amend RMD ages, catch-up rules, distribution triggers, or vesting schedules
3. **DOL issues new regulations or PTEs** — prohibited transaction exemptions, cybersecurity guidance, fee disclosure rules
4. **IRS issues guidance** — e.g., SECURE 2.0 Roth catch-up effective date guidance, spousal consent waiver rules

When the master reference is updated, the `fap.erisa_ref.update_required` event must be fired to alert the compliance team before the new version is deployed.

---

## Non-Goals

- FAP does not execute participant transactions (that is PAAP)
- FAP does not store or serve plan data (that is PLAP)
- FAP does not make investment recommendations or give financial advice
- FAP does not adjudicate legal disputes — it flags and blocks; human review handles adjudication
