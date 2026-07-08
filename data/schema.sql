-- Aldergate ERISA 401(k) Administration — PostgreSQL Schema
-- All monetary amounts use DECIMAL(14,2) — never FLOAT for money.
-- fap_audit_log is append-only; enforce at DB level in production:
--   REVOKE DELETE, UPDATE ON fap_audit_log FROM aldergate_app;

-- ============================================================
-- PLANS
-- ============================================================

CREATE TABLE plans (
    plan_id                         VARCHAR(64)     PRIMARY KEY,
    plan_name                       VARCHAR(256)    NOT NULL,
    plan_type                       VARCHAR(16)     NOT NULL,   -- 401k, 403b, 457b, DB, ESOP
    safe_harbor                     BOOLEAN         NOT NULL DEFAULT FALSE,
    erisa_plan_number               VARCHAR(32)     NOT NULL,
    ein                             VARCHAR(10),               -- employer EIN (xx-xxxxxxx)
    effective_date                  DATE            NOT NULL,
    plan_year_end                   VARCHAR(5)      NOT NULL DEFAULT '12/31',

    -- Eligibility — ERISA § 202 / IRC § 410(a)
    eligibility_age                 INT             NOT NULL DEFAULT 21,   -- max 21 per ERISA; plans may set lower
    eligibility_months_of_service   INT             NOT NULL DEFAULT 12,   -- 0 = immediate; max 12 months per ERISA

    -- Employer match (multi-tier JSON): { tiers: [{rate, on_first_pct}, ...], true_up: bool }
    employer_match                  JSONB,

    snapshot_version                VARCHAR(16)     NOT NULL DEFAULT '1.0',
    created_at                      TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at                      TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_plans_plan_type ON plans(plan_type);


-- ============================================================
-- VESTING SCHEDULES
-- ============================================================

CREATE TABLE plan_vesting_schedules (
    id                          SERIAL          PRIMARY KEY,
    plan_id                     VARCHAR(64)     NOT NULL REFERENCES plans(plan_id) ON DELETE CASCADE,
    vesting_type                VARCHAR(16)     NOT NULL CHECK (vesting_type IN ('immediate','cliff','graduated')),
    cliff_years                 INT,                            -- required if vesting_type = cliff
    service_crediting_method    VARCHAR(32)     NOT NULL DEFAULT 'hours_of_service',
    is_match_schedule           BOOLEAN         NOT NULL DEFAULT TRUE,  -- FALSE = profit-sharing schedule
    created_at                  TIMESTAMPTZ     NOT NULL DEFAULT NOW(),

    UNIQUE (plan_id, is_match_schedule)
);

-- Graduated vesting breakpoints — only used when vesting_type = graduated
CREATE TABLE plan_vesting_breakpoints (
    id              SERIAL      PRIMARY KEY,
    schedule_id     INT         NOT NULL REFERENCES plan_vesting_schedules(id) ON DELETE CASCADE,
    year            INT         NOT NULL CHECK (year > 0),
    pct             DECIMAL(5,4) NOT NULL CHECK (pct >= 0 AND pct <= 1),
    UNIQUE (schedule_id, year)
);


-- ============================================================
-- LOAN POLICY
-- ============================================================

CREATE TABLE plan_loan_policy (
    plan_id                         VARCHAR(64)     PRIMARY KEY REFERENCES plans(plan_id) ON DELETE CASCADE,
    loans_permitted                 BOOLEAN         NOT NULL DEFAULT FALSE,
    max_loan_amount                 INT             NOT NULL DEFAULT 50000,  -- IRC § 72(p) cap
    max_loan_pct_of_vested          DECIMAL(5,4)    NOT NULL DEFAULT 0.50,
    min_loan_amount                 INT             NOT NULL DEFAULT 1000,
    max_repayment_years_general     INT             NOT NULL DEFAULT 5,
    max_repayment_years_primary_res INT             NOT NULL DEFAULT 15,
    outstanding_loans_permitted     INT             NOT NULL DEFAULT 1,
    origination_fee                 DECIMAL(8,2)    NOT NULL DEFAULT 0.00,
    quarterly_maintenance_fee       DECIMAL(8,2)    NOT NULL DEFAULT 0.00,
    cooldown_days_after_repayment   INT             NOT NULL DEFAULT 0,
    updated_at                      TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);


-- ============================================================
-- HARDSHIP POLICY
-- ============================================================

CREATE TABLE plan_hardship_policy (
    plan_id                             VARCHAR(64)     PRIMARY KEY REFERENCES plans(plan_id) ON DELETE CASCADE,
    hardship_permitted                  BOOLEAN         NOT NULL DEFAULT FALSE,
    hardship_standard                   VARCHAR(32)     NOT NULL DEFAULT 'safe_harbor',
    qualifying_expenses                 JSONB           NOT NULL DEFAULT '[]',   -- array of QualifyingExpenseType strings
    six_month_contribution_suspension   BOOLEAN         NOT NULL DEFAULT FALSE,
    updated_at                          TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);


-- ============================================================
-- DISTRIBUTION OPTIONS
-- ============================================================

CREATE TABLE plan_distribution_options (
    plan_id                             VARCHAR(64)     PRIMARY KEY REFERENCES plans(plan_id) ON DELETE CASCADE,
    in_service_age_59_5                 BOOLEAN         NOT NULL DEFAULT TRUE,
    normal_retirement_age               INT             NOT NULL DEFAULT 65,
    early_retirement_age                INT,
    rmd_start_rule                      VARCHAR(16)     NOT NULL DEFAULT 'age_73',
    rmd_calculation_method              VARCHAR(32)     NOT NULL DEFAULT 'uniform_lifetime',
    qjsa_survivor_pct                   DECIMAL(5,4)    NOT NULL DEFAULT 0.50,
    qjsa_waiver_requires_spousal_consent BOOLEAN        NOT NULL DEFAULT TRUE,

    -- Rollover / QDRO
    accepts_rollover_in                 BOOLEAN         NOT NULL DEFAULT TRUE,
    rollover_in_sources                 JSONB           NOT NULL DEFAULT '["traditional_ira","employer_plan","roth_401k"]',
    direct_rollover_out_permitted       BOOLEAN         NOT NULL DEFAULT TRUE,
    qdro_procedures_url                 TEXT,
    qdro_required_fields                JSONB           NOT NULL DEFAULT '["participant_name","alternate_payee_name","plan_name","benefit_amount_or_pct","payment_period"]',

    -- Blackout period (can change without altering plan core)
    blackout_is_active                  BOOLEAN         NOT NULL DEFAULT FALSE,
    blackout_start_date                 DATE,
    blackout_end_date                   DATE,
    blackout_reason                     TEXT,
    updated_at                          TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);


-- ============================================================
-- INVESTMENT FUND LINEUP
-- ============================================================

CREATE TABLE plan_funds (
    id              SERIAL          PRIMARY KEY,
    plan_id         VARCHAR(64)     NOT NULL REFERENCES plans(plan_id) ON DELETE CASCADE,
    fund_id         VARCHAR(64)     NOT NULL,
    fund_name       VARCHAR(256)    NOT NULL,
    ticker          VARCHAR(16),
    asset_class     VARCHAR(64)     NOT NULL,
    expense_ratio   DECIMAL(6,4)    NOT NULL CHECK (expense_ratio >= 0),
    is_qdia         BOOLEAN         NOT NULL DEFAULT FALSE,
    is_stable_value BOOLEAN         NOT NULL DEFAULT FALSE,
    available_from  DATE,
    available_to    DATE,

    UNIQUE (plan_id, fund_id)
);

CREATE INDEX idx_plan_funds_plan_id ON plan_funds(plan_id);


-- ============================================================
-- PARTICIPANTS
-- ============================================================

CREATE TABLE participants (
    participant_id              VARCHAR(64)     PRIMARY KEY,
    plan_id                     VARCHAR(64)     NOT NULL REFERENCES plans(plan_id),

    -- PII — never store raw SSN; encrypt remaining PII at rest in production
    ssn_hash                    VARCHAR(128)    NOT NULL UNIQUE,  -- SHA-256 of SSN
    -- first_name, last_name, dob stored encrypted; column type BYTEA in production
    -- For Phase 2 (dev) we store plaintext; Phase 6 adds encryption
    first_name                  VARCHAR(128)    NOT NULL,
    last_name                   VARCHAR(128)    NOT NULL,
    date_of_birth               DATE            NOT NULL,     -- never expose raw; FAP resolves to age boolean

    -- Employment
    date_of_hire                DATE            NOT NULL,
    eligibility_date            DATE            NOT NULL,
    employment_status           VARCHAR(32)     NOT NULL DEFAULT 'active'
                                    CHECK (employment_status IN ('active','terminated','retired','on_leave','military_leave')),
    termination_date            DATE,
    years_of_vesting_service    DECIMAL(5,2)    NOT NULL DEFAULT 0.00,
    hours_of_service_ytd        INT             NOT NULL DEFAULT 0,
    break_in_service            BOOLEAN         NOT NULL DEFAULT FALSE,
    userra_military_leave       BOOLEAN         NOT NULL DEFAULT FALSE,

    -- Account balances
    total_balance               DECIMAL(14,2)   NOT NULL DEFAULT 0.00,
    vested_balance              DECIMAL(14,2)   NOT NULL DEFAULT 0.00,
    vesting_percentage          DECIMAL(5,4)    NOT NULL DEFAULT 0.00 CHECK (vesting_percentage >= 0 AND vesting_percentage <= 1),
    employee_contributions_ytd  DECIMAL(14,2)   NOT NULL DEFAULT 0.00,
    employer_contributions_ytd  DECIMAL(14,2)   NOT NULL DEFAULT 0.00,

    -- Deferrals
    current_deferral_pct        DECIMAL(5,4)    NOT NULL DEFAULT 0.00,
    deferral_type               VARCHAR(16)     NOT NULL DEFAULT 'pre_tax'
                                    CHECK (deferral_type IN ('pre_tax','roth','after_tax')),

    -- Compensation
    compensation_ytd            DECIMAL(14,2)   NOT NULL DEFAULT 0.00,

    -- Compliance flags
    is_hce                      BOOLEAN         NOT NULL DEFAULT FALSE,
    age_50_or_older             BOOLEAN         NOT NULL DEFAULT FALSE,
    age_60_to_63                BOOLEAN         NOT NULL DEFAULT FALSE,   -- SECURE 2.0 enhanced catch-up window

    -- RMD
    rmd_required                BOOLEAN         NOT NULL DEFAULT FALSE,
    rmd_amount_current_year     DECIMAL(14,2),
    rmd_due_date                DATE,

    created_at                  TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at                  TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_participants_plan_id ON participants(plan_id);
CREATE INDEX idx_participants_ssn_hash ON participants(ssn_hash);
CREATE INDEX idx_participants_employment_status ON participants(plan_id, employment_status);


-- ============================================================
-- PARTICIPANT LOANS
-- ============================================================

CREATE TABLE participant_loans (
    loan_id                         VARCHAR(64)     PRIMARY KEY,
    participant_id                  VARCHAR(64)     NOT NULL REFERENCES participants(participant_id),
    plan_id                         VARCHAR(64)     NOT NULL REFERENCES plans(plan_id),
    loan_type                       VARCHAR(32)     NOT NULL DEFAULT 'general'
                                        CHECK (loan_type IN ('general','primary_residence')),
    original_amount                 DECIMAL(14,2)   NOT NULL CHECK (original_amount > 0),
    outstanding_balance             DECIMAL(14,2)   NOT NULL CHECK (outstanding_balance >= 0),
    highest_balance_last_12_months  DECIMAL(14,2)   NOT NULL CHECK (highest_balance_last_12_months >= 0),
    interest_rate                   DECIMAL(6,4)    NOT NULL CHECK (interest_rate >= 0),
    origination_date                DATE            NOT NULL,
    maturity_date                   DATE            NOT NULL,
    payment_amount                  DECIMAL(14,2)   NOT NULL CHECK (payment_amount > 0),
    payment_frequency               VARCHAR(16)     NOT NULL DEFAULT 'monthly'
                                        CHECK (payment_frequency IN ('weekly','biweekly','monthly')),
    status                          VARCHAR(32)     NOT NULL DEFAULT 'active'
                                        CHECK (status IN ('active','repaid','defaulted','deemed_distributed')),
    repaid_date                     DATE,
    created_at                      TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at                      TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_participant_loans_participant_id ON participant_loans(participant_id);
CREATE INDEX idx_participant_loans_status ON participant_loans(participant_id, status);


-- ============================================================
-- PARTICIPANT INVESTMENT ELECTIONS
-- ============================================================

CREATE TABLE participant_investment_elections (
    id              SERIAL          PRIMARY KEY,
    participant_id  VARCHAR(64)     NOT NULL REFERENCES participants(participant_id),
    plan_id         VARCHAR(64)     NOT NULL REFERENCES plans(plan_id),
    fund_id         VARCHAR(64)     NOT NULL,
    allocation_pct  DECIMAL(6,4)    NOT NULL CHECK (allocation_pct >= 0 AND allocation_pct <= 1),
    effective_date  DATE            NOT NULL,

    UNIQUE (participant_id, fund_id, effective_date)
);

CREATE INDEX idx_elections_participant ON participant_investment_elections(participant_id, effective_date DESC);


-- ============================================================
-- AGENT REGISTRY
-- ============================================================

CREATE TABLE agent_registry (
    agent_id            VARCHAR(64)     PRIMARY KEY,
    agent_name          VARCHAR(256)    NOT NULL,
    principal_type      VARCHAR(32)     NOT NULL
                            CHECK (principal_type IN ('participant','plan_sponsor','investment_advisor','plan_trustee','participant_delegate')),
    allowed_actions     JSONB           NOT NULL DEFAULT '[]',  -- array of ActionType strings; ["*"] for wildcard
    allowed_plan_ids    JSONB           NOT NULL DEFAULT '[]',  -- array of plan_ids; ["*"] for all plans
    is_active           BOOLEAN         NOT NULL DEFAULT TRUE,
    registered_at       TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    revoked_at          TIMESTAMPTZ
);

CREATE INDEX idx_agent_registry_active ON agent_registry(is_active) WHERE is_active = TRUE;


-- ============================================================
-- FAP TOKENS  (single-use enforcement)
-- ============================================================

CREATE TABLE fap_tokens (
    token_id        UUID            PRIMARY KEY,
    issued_at       TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    expires_at      TIMESTAMPTZ     NOT NULL,
    consumed_at     TIMESTAMPTZ,
    consumed        BOOLEAN         NOT NULL DEFAULT FALSE,

    -- Scope mirrors the JWT payload claims
    agent_id        VARCHAR(64)     NOT NULL,
    participant_id  VARCHAR(64),
    plan_id         VARCHAR(64),
    action          VARCHAR(64)     NOT NULL,
    payload_hash    VARCHAR(128)    NOT NULL,   -- SHA-256 of request payload

    -- Back-reference to audit record
    audit_id        UUID
);

CREATE INDEX idx_fap_tokens_consumed ON fap_tokens(consumed, expires_at);


-- ============================================================
-- FAP AUDIT LOG  (immutable — ERISA § 107 requires 6-year retention)
-- In production: REVOKE DELETE, UPDATE ON fap_audit_log FROM aldergate_app;
-- ============================================================

CREATE TABLE fap_audit_log (
    audit_id            UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW(),

    -- Who / what
    agent_id            VARCHAR(64)     NOT NULL,
    principal_type      VARCHAR(32)     NOT NULL,
    participant_id      VARCHAR(64),
    plan_id             VARCHAR(64),
    action              VARCHAR(64)     NOT NULL,

    -- What was requested
    payload_hash        VARCHAR(128)    NOT NULL,   -- SHA-256; never store raw payload (may contain PII)

    -- Outcome
    outcome             VARCHAR(16)     NOT NULL CHECK (outcome IN ('approved','denied')),
    autonomy_level      VARCHAR(16),               -- full / supervised / human_review (approved only)
    denial_code         VARCHAR(64),               -- denied only
    erisa_citation      TEXT,
    master_ref_section  VARCHAR(32),

    -- Rule trace (for audit trail and debugging)
    rules_passed        INT[]           NOT NULL DEFAULT '{}',
    rule_failed         INT,
    conditions          TEXT[]          NOT NULL DEFAULT '{}',

    -- Issued token (approved only)
    token_id            UUID,

    -- Request tracing
    request_id          UUID,
    ip_address          INET
);

-- Partial index for open human_review items (operational dashboard)
CREATE INDEX idx_audit_human_review
    ON fap_audit_log(created_at DESC)
    WHERE outcome = 'approved' AND autonomy_level = 'human_review';

-- Retention index — used by scheduled purge job (must not purge before 6 years)
CREATE INDEX idx_audit_created_at ON fap_audit_log(created_at);
