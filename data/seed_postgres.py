"""
Aldergate PostgreSQL Seed Script
=================================
Populates all tables with real plan data extracted from SPDs.

Plans
  PLAN-003  Capital One Financial Corporation Associate Savings Plan  (from SPD, effective Jan 1 2024)
  PLAN-004  The Prudential Employee Savings Plan (PESP)               (from SPD, 2023)

Participants (5)
  PART-006  Gabriel Stone   — PLAN-003 Capital One, age 62, HCE, active employee
  PART-007  Yuki Tanaka     — PLAN-004 Prudential, age 31, 1.5yr service, cliff not yet met
  PART-008  Amara Osei      — PLAN-003 Capital One, age 36, primary demo participant
  PART-009  Daniela Reyes   — PLAN-003 Capital One, age 41, existing $25k loan
  PART-010  Eleanor Walsh   — PLAN-003 Capital One, age 75, retired, rmd_required=True

Run:
  python data/seed_postgres.py
"""

import hashlib
import json
import os
import sys

import psycopg2
from psycopg2.extras import Json

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://devanshsaroja@localhost:5432/aldergate",
)


def connect():
    return psycopg2.connect(DATABASE_URL)


# ---------------------------------------------------------------------------
# Plans
# ---------------------------------------------------------------------------

PLANS = [
    {
        # Extracted from Capital One Associate Savings Plan SPD (effective Jan 1, 2024)
        "plan_id": "PLAN-003",
        "plan_name": "Capital One Financial Corporation Associate Savings Plan",
        "plan_type": "401k",
        "safe_harbor": True,           # design-based safe harbor (IRC § 401(k)(12))
        "erisa_plan_number": "002",
        "ein": "54-1719854",
        "effective_date": "1995-01-01",
        "plan_year_end": "12/31",
        "eligibility_age": 18,
        "eligibility_months_of_service": 0,   # immediate eligibility on hire
        # 3% Basic Non-Elective always paid + 100% on first 3% + 50% on next 3% (max 7.5% total)
        "employer_match": {
            "tiers": [
                {"rate": 1.0, "on_first_pct": 0.03},
                {"rate": 0.5, "on_next_pct": 0.03},
            ],
            "non_elective_pct": 0.03,
            "true_up": True,
        },
        "snapshot_version": "1.0",
    },
    {
        # Extracted from Prudential Employee Savings Plan (PESP) SPD (2023)
        "plan_id": "PLAN-004",
        "plan_name": "The Prudential Employee Savings Plan",
        "plan_type": "401k",
        "safe_harbor": False,
        "erisa_plan_number": "002",
        "ein": "22-1211670",
        "effective_date": "1970-07-01",
        "plan_year_end": "12/31",
        "eligibility_age": 21,
        "eligibility_months_of_service": 12,
        # 100% match on first 4% of compensation
        "employer_match": {
            "tiers": [{"rate": 1.0, "on_first_pct": 0.04}],
            "true_up": False,
        },
        "snapshot_version": "1.0",
    },
]

VESTING_SCHEDULES = [
    # PLAN-003 Capital One — 2-year cliff for match; employee + non-elective are immediate
    {
        "plan_id": "PLAN-003",
        "vesting_type": "cliff",
        "cliff_years": 2,
        "service_crediting_method": "hours_of_service",
        "is_match_schedule": True,
    },
    # PLAN-004 Prudential PESP — 3-year cliff for match
    {
        "plan_id": "PLAN-004",
        "vesting_type": "cliff",
        "cliff_years": 3,
        "service_crediting_method": "hours_of_service",
        "is_match_schedule": True,
    },
]

LOAN_POLICIES = [
    {
        # Capital One: $1,000 min, 50% / $50k max, 2 loans, 5yr general / 10yr primary res, $50 setup fee
        "plan_id": "PLAN-003",
        "loans_permitted": True,
        "max_loan_amount": 50000,
        "max_loan_pct_of_vested": 0.50,
        "min_loan_amount": 1000,
        "max_repayment_years_general": 5,
        "max_repayment_years_primary_res": 10,
        "outstanding_loans_permitted": 2,
        "origination_fee": 50.00,
        "quarterly_maintenance_fee": 0.00,
        "cooldown_days_after_repayment": 0,
    },
    {
        # Prudential PESP: $500 min, 50% / $50k max, 1 loan, 5yr general / 15yr primary res
        "plan_id": "PLAN-004",
        "loans_permitted": True,
        "max_loan_amount": 50000,
        "max_loan_pct_of_vested": 0.50,
        "min_loan_amount": 500,
        "max_repayment_years_general": 5,
        "max_repayment_years_primary_res": 15,
        "outstanding_loans_permitted": 1,
        "origination_fee": 0.00,
        "quarterly_maintenance_fee": 0.00,
        "cooldown_days_after_repayment": 0,
    },
]

IRS_HARDSHIP_EXPENSES = json.dumps([
    "medical", "tuition", "primary_home_purchase",
    "prevent_eviction", "funeral", "casualty_loss", "fema_disaster",
])

HARDSHIP_POLICIES = [
    {
        # Capital One: all 7 IRS safe harbor categories (per SPD §6)
        "plan_id": "PLAN-003",
        "hardship_permitted": True,
        "hardship_standard": "safe_harbor",
        "qualifying_expenses": IRS_HARDSHIP_EXPENSES,
        "six_month_contribution_suspension": False,
    },
    {
        # Prudential PESP: safe harbor 7 IRS categories
        "plan_id": "PLAN-004",
        "hardship_permitted": True,
        "hardship_standard": "safe_harbor",
        "qualifying_expenses": IRS_HARDSHIP_EXPENSES,
        "six_month_contribution_suspension": False,
    },
]

DISTRIBUTION_OPTIONS = [
    {
        # Capital One: in-service 59½, NRA 65, RMD age 73
        "plan_id": "PLAN-003",
        "in_service_age_59_5": True,
        "normal_retirement_age": 65,
        "early_retirement_age": None,
        "rmd_start_rule": "age_73",
        "rmd_calculation_method": "uniform_lifetime",
        "qjsa_survivor_pct": 0.50,
        "qjsa_waiver_requires_spousal_consent": True,
        "accepts_rollover_in": True,
        "rollover_in_sources": json.dumps(["traditional_ira", "employer_plan", "roth_401k"]),
        "direct_rollover_out_permitted": True,
        "qdro_procedures_url": None,
        "qdro_required_fields": json.dumps([
            "participant_name", "alternate_payee_name", "plan_name",
            "benefit_amount_or_pct", "payment_period",
        ]),
        "blackout_is_active": False,
        "blackout_start_date": None,
        "blackout_end_date": None,
        "blackout_reason": None,
    },
    {
        # Prudential PESP: in-service 59½, NRA 65, RMD age 73
        "plan_id": "PLAN-004",
        "in_service_age_59_5": True,
        "normal_retirement_age": 65,
        "early_retirement_age": None,
        "rmd_start_rule": "age_73",
        "rmd_calculation_method": "uniform_lifetime",
        "qjsa_survivor_pct": 0.50,
        "qjsa_waiver_requires_spousal_consent": True,
        "accepts_rollover_in": True,
        "rollover_in_sources": json.dumps(["traditional_ira", "employer_plan", "roth_401k"]),
        "direct_rollover_out_permitted": True,
        "qdro_procedures_url": None,
        "qdro_required_fields": json.dumps([
            "participant_name", "alternate_payee_name", "plan_name",
            "benefit_amount_or_pct", "payment_period",
        ]),
        "blackout_is_active": False,
        "blackout_start_date": None,
        "blackout_end_date": None,
        "blackout_reason": None,
    },
]

FUND_LINEUPS = {
    "PLAN-003": [
        # Capital One fund lineup — Fidelity recordkeeper, BlackRock LifePath QDIA
        {"fund_id": "COF-LIFEPATH-2025", "fund_name": "BlackRock LifePath Index 2025 Fund",   "ticker": "LIPAX", "asset_class": "Target Date",        "expense_ratio": 0.0012, "is_qdia": True,  "is_stable_value": False},
        {"fund_id": "COF-LIFEPATH-2030", "fund_name": "BlackRock LifePath Index 2030 Fund",   "ticker": "LIBAX", "asset_class": "Target Date",        "expense_ratio": 0.0012, "is_qdia": True,  "is_stable_value": False},
        {"fund_id": "COF-LIFEPATH-2035", "fund_name": "BlackRock LifePath Index 2035 Fund",   "ticker": "LINKX", "asset_class": "Target Date",        "expense_ratio": 0.0012, "is_qdia": True,  "is_stable_value": False},
        {"fund_id": "COF-LIFEPATH-2040", "fund_name": "BlackRock LifePath Index 2040 Fund",   "ticker": "LIMAX", "asset_class": "Target Date",        "expense_ratio": 0.0012, "is_qdia": True,  "is_stable_value": False},
        {"fund_id": "COF-LIFEPATH-2045", "fund_name": "BlackRock LifePath Index 2045 Fund",   "ticker": "LINOX", "asset_class": "Target Date",        "expense_ratio": 0.0012, "is_qdia": True,  "is_stable_value": False},
        {"fund_id": "COF-LIFEPATH-2050", "fund_name": "BlackRock LifePath Index 2050 Fund",   "ticker": "LIPIX", "asset_class": "Target Date",        "expense_ratio": 0.0012, "is_qdia": True,  "is_stable_value": False},
        {"fund_id": "COF-SP500",         "fund_name": "Fidelity 500 Index Fund",              "ticker": "FXAIX", "asset_class": "US Large Cap Equity", "expense_ratio": 0.0015, "is_qdia": False, "is_stable_value": False},
        {"fund_id": "COF-RUSSELL2500",   "fund_name": "Vanguard Extended Market Index Fund",  "ticker": "VEXAX", "asset_class": "US Mid/Small Cap",   "expense_ratio": 0.0006, "is_qdia": False, "is_stable_value": False},
        {"fund_id": "COF-INTL",          "fund_name": "Fidelity Total International Index",   "ticker": "FTIHX", "asset_class": "International",      "expense_ratio": 0.0006, "is_qdia": False, "is_stable_value": False},
        {"fund_id": "COF-BOND",          "fund_name": "Fidelity U.S. Bond Index Fund",        "ticker": "FXNAX", "asset_class": "Fixed Income",        "expense_ratio": 0.0003, "is_qdia": False, "is_stable_value": False},
        {"fund_id": "COF-STABLE",        "fund_name": "Fidelity Managed Income Portfolio II", "ticker": None,    "asset_class": "Stable Value",        "expense_ratio": 0.0042, "is_qdia": False, "is_stable_value": True},
        {"fund_id": "COF-CAPON",         "fund_name": "Capital One Financial Corp. Stock",    "ticker": "COF",   "asset_class": "Company Stock",       "expense_ratio": 0.0000, "is_qdia": False, "is_stable_value": False},
    ],
    "PLAN-004": [
        # Prudential PESP — Empower recordkeeper, GoalMaker QDIA models
        {"fund_id": "PESP-GOALMAKER-CONS", "fund_name": "GoalMaker Conservative Portfolio",       "ticker": None,    "asset_class": "Target Date",        "expense_ratio": 0.0045, "is_qdia": True,  "is_stable_value": False},
        {"fund_id": "PESP-GOALMAKER-MOD",  "fund_name": "GoalMaker Moderate Portfolio",           "ticker": None,    "asset_class": "Target Date",        "expense_ratio": 0.0045, "is_qdia": True,  "is_stable_value": False},
        {"fund_id": "PESP-GOALMAKER-AGG",  "fund_name": "GoalMaker Aggressive Portfolio",         "ticker": None,    "asset_class": "Target Date",        "expense_ratio": 0.0045, "is_qdia": True,  "is_stable_value": False},
        {"fund_id": "PESP-SP500",          "fund_name": "Vanguard Institutional 500 Index Trust", "ticker": "VINIX", "asset_class": "US Large Cap Equity", "expense_ratio": 0.0003, "is_qdia": False, "is_stable_value": False},
        {"fund_id": "PESP-SMIDCAP",        "fund_name": "Vanguard Extended Market Index Fund",    "ticker": "VEXAX", "asset_class": "US Mid/Small Cap",   "expense_ratio": 0.0006, "is_qdia": False, "is_stable_value": False},
        {"fund_id": "PESP-INTL",           "fund_name": "Vanguard Total International Stock",     "ticker": "VTIAX", "asset_class": "International",      "expense_ratio": 0.0011, "is_qdia": False, "is_stable_value": False},
        {"fund_id": "PESP-BOND",           "fund_name": "PGIM Core Plus Bond Fund",               "ticker": "TAIBX", "asset_class": "Fixed Income",        "expense_ratio": 0.0043, "is_qdia": False, "is_stable_value": False},
        {"fund_id": "PESP-STABLE",         "fund_name": "Prudential Guaranteed Income Fund",      "ticker": None,    "asset_class": "Stable Value",        "expense_ratio": 0.0040, "is_qdia": False, "is_stable_value": True},
        {"fund_id": "PESP-PRU-STOCK",      "fund_name": "Prudential Financial Inc. Stock Fund",   "ticker": "PRU",   "asset_class": "Company Stock",       "expense_ratio": 0.0000, "is_qdia": False, "is_stable_value": False},
    ],
}

# ---------------------------------------------------------------------------
# Agent Registry
# ---------------------------------------------------------------------------

AGENTS = [
    {
        "agent_id": "AGENT-PARTICIPANT-001",
        "agent_name": "Participant Self-Service Agent",
        "principal_type": "participant",
        "allowed_actions": json.dumps(["*"]),
        "allowed_plan_ids": json.dumps(["PLAN-003", "PLAN-004"]),
        "is_active": True,
    },
    {
        "agent_id": "AGENT-ADVISOR-001",
        "agent_name": "Registered Investment Advisor Agent",
        "principal_type": "investment_advisor",
        "allowed_actions": json.dumps(["investment_reallocation", "deferral_change"]),
        "allowed_plan_ids": json.dumps(["PLAN-003"]),
        "is_active": True,
    },
    {
        "agent_id": "AGENT-SPONSOR-001",
        "agent_name": "Plan Sponsor Admin Agent",
        "principal_type": "plan_sponsor",
        "allowed_actions": json.dumps(["beneficiary_update", "qdro", "rmd"]),
        "allowed_plan_ids": json.dumps(["*"]),
        "is_active": True,
    },
    {
        "agent_id": "AGENT-INACTIVE-001",
        "agent_name": "Revoked Agent",
        "principal_type": "participant",
        "allowed_actions": json.dumps(["*"]),
        "allowed_plan_ids": json.dumps(["PLAN-003"]),
        "is_active": False,
    },
]

# ---------------------------------------------------------------------------
# Participants
# ---------------------------------------------------------------------------

def _ssn_hash(n: str) -> str:
    return "sha256:" + hashlib.sha256(n.encode()).hexdigest()


PARTICIPANTS = [
    {
        # Capital One — age 62, HCE, active, 27yr service
        # Used for: catch-up / Roth SECURE 2.0 tests, in-service distribution (over 59½)
        "participant_id": "PART-006",
        "plan_id": "PLAN-003",
        "ssn_hash": _ssn_hash("FAKE-SSN-006"),
        "first_name": "Gabriel",
        "last_name": "Stone",
        "date_of_birth": "1964-04-15",           # age 62
        "date_of_hire": "1998-03-01",
        "eligibility_date": "1998-03-01",          # immediate eligibility on Capital One
        "employment_status": "active",
        "termination_date": None,
        "years_of_vesting_service": 27.0,
        "hours_of_service_ytd": 1750,
        "break_in_service": False,
        "userra_military_leave": False,
        "total_balance": 225000.00,
        "vested_balance": 210000.00,
        "vesting_percentage": 1.0,
        "employee_contributions_ytd": 23000.00,
        "employer_contributions_ytd": 10350.00,
        "current_deferral_pct": 0.10,
        "deferral_type": "pre_tax",
        "compensation_ytd": 185000.00,
        "is_hce": True,
        "age_50_or_older": True,
        "age_60_to_63": True,
        "rmd_required": False,
        "rmd_amount_current_year": None,
        "rmd_due_date": None,
        "elections": [
            {"fund_id": "COF-LIFEPATH-2030", "allocation_pct": 0.60},
            {"fund_id": "COF-SP500",          "allocation_pct": 0.25},
            {"fund_id": "COF-STABLE",         "allocation_pct": 0.15},
        ],
    },
    {
        # Prudential PESP — age 31, 1.5yr service, vesting cliff NOT met (3yr cliff)
        # Also unvested on Capital One (2yr cliff). Used for: vesting Rule 4 fail tests.
        "participant_id": "PART-007",
        "plan_id": "PLAN-004",
        "ssn_hash": _ssn_hash("FAKE-SSN-007"),
        "first_name": "Yuki",
        "last_name": "Tanaka",
        "date_of_birth": "1994-12-05",            # age 31
        "date_of_hire": "2024-07-01",
        "eligibility_date": "2025-07-01",          # 1yr wait (Prudential)
        "employment_status": "active",
        "termination_date": None,
        "years_of_vesting_service": 1.5,           # below both 2yr and 3yr cliffs
        "hours_of_service_ytd": 1100,
        "break_in_service": False,
        "userra_military_leave": False,
        "total_balance": 42000.00,
        "vested_balance": 38000.00,
        "vesting_percentage": 0.0,                 # 0% vested in employer match (cliff not met)
        "employee_contributions_ytd": 4000.00,
        "employer_contributions_ytd": 4000.00,
        "current_deferral_pct": 0.04,
        "deferral_type": "pre_tax",
        "compensation_ytd": 72000.00,
        "is_hce": False,
        "age_50_or_older": False,
        "age_60_to_63": False,
        "rmd_required": False,
        "rmd_amount_current_year": None,
        "rmd_due_date": None,
        "elections": [
            {"fund_id": "PESP-GOALMAKER-MOD", "allocation_pct": 1.0},
        ],
    },
    {
        # Capital One — age 36, primary demo participant
        # Fully eligible (immediate eligibility), 5yr service (> 2yr cliff = fully vested),
        # no loans, under 59½ — used as the baseline participant in most compliance tests.
        "participant_id": "PART-008",
        "plan_id": "PLAN-003",
        "ssn_hash": _ssn_hash("FAKE-SSN-008"),
        "first_name": "Amara",
        "last_name": "Osei",
        "date_of_birth": "1990-02-18",            # age 36
        "date_of_hire": "2021-03-01",
        "eligibility_date": "2021-03-01",          # immediate eligibility
        "employment_status": "active",
        "termination_date": None,
        "years_of_vesting_service": 5.0,
        "hours_of_service_ytd": 1200,
        "break_in_service": False,
        "userra_military_leave": False,
        "total_balance": 92000.00,
        "vested_balance": 85000.00,
        "vesting_percentage": 1.0,                 # fully vested (5yr > 2yr Capital One cliff)
        "employee_contributions_ytd": 8000.00,
        "employer_contributions_ytd": 5060.00,
        "current_deferral_pct": 0.06,
        "deferral_type": "pre_tax",
        "compensation_ytd": 92000.00,
        "is_hce": False,
        "age_50_or_older": False,
        "age_60_to_63": False,
        "rmd_required": False,
        "rmd_amount_current_year": None,
        "rmd_due_date": None,
        "elections": [
            {"fund_id": "COF-LIFEPATH-2055", "allocation_pct": 0.70} if False else
            {"fund_id": "COF-LIFEPATH-2040", "allocation_pct": 0.70},
            {"fund_id": "COF-SP500", "allocation_pct": 0.30},
        ],
    },
    {
        # Capital One — age 75, retired 2016-03-10 (at NRA 65), rmd_required=True
        # Used for: RMD happy path, RMD denial (amount below minimum)
        # IRS Uniform Lifetime Table age 75 → distribution period 24.6
        # RMD 2026 = $400,000 (prior year-end vested) / 24.6 = $16,260
        "participant_id": "PART-010",
        "plan_id": "PLAN-003",
        "ssn_hash": _ssn_hash("FAKE-SSN-010"),
        "first_name": "Eleanor",
        "last_name": "Walsh",
        "date_of_birth": "1951-03-10",            # age 75
        "date_of_hire": "1980-01-15",
        "eligibility_date": "1980-01-15",
        "employment_status": "retired",
        "termination_date": "2016-03-10",          # retired at NRA 65
        "years_of_vesting_service": 36.0,
        "hours_of_service_ytd": 0,                 # retired — no current hours
        "break_in_service": False,
        "userra_military_leave": False,
        "total_balance": 415000.00,
        "vested_balance": 400000.00,
        "vesting_percentage": 1.0,
        "employee_contributions_ytd": 0.00,        # retired — no active contributions
        "employer_contributions_ytd": 0.00,
        "current_deferral_pct": 0.00,
        "deferral_type": "pre_tax",
        "compensation_ytd": 0.00,
        "is_hce": False,
        "age_50_or_older": True,
        "age_60_to_63": False,
        "rmd_required": True,
        "rmd_amount_current_year": 16260.00,       # $400k / 24.6 (IRS Uniform Lifetime Table, age 75)
        "rmd_due_date": "2026-12-31",
        "elections": [
            {"fund_id": "COF-LIFEPATH-2025", "allocation_pct": 0.50},
            {"fund_id": "COF-BOND",          "allocation_pct": 0.30},
            {"fund_id": "COF-STABLE",        "allocation_pct": 0.20},
        ],
    },
    {
        # Capital One — age 41, terminated 2026-03-01, existing $25k loan
        # Used for: IRC §72(p) cap math demo, separation distribution demo
        "participant_id": "PART-009",
        "plan_id": "PLAN-003",
        "ssn_hash": _ssn_hash("FAKE-SSN-009"),
        "first_name": "Daniela",
        "last_name": "Reyes",
        "date_of_birth": "1985-09-14",            # age 41
        "date_of_hire": "2014-04-01",
        "eligibility_date": "2014-04-01",
        "employment_status": "terminated",
        "termination_date": "2026-03-01",
        "years_of_vesting_service": 10.0,
        "hours_of_service_ytd": 1600,
        "break_in_service": False,
        "userra_military_leave": False,
        "total_balance": 105000.00,
        "vested_balance": 100000.00,
        "vesting_percentage": 1.0,
        "employee_contributions_ytd": 12000.00,
        "employer_contributions_ytd": 5000.00,
        "current_deferral_pct": 0.08,
        "deferral_type": "pre_tax",
        "compensation_ytd": 88000.00,
        "is_hce": False,
        "age_50_or_older": False,
        "age_60_to_63": False,
        "rmd_required": False,
        "rmd_amount_current_year": None,
        "rmd_due_date": None,
        "elections": [
            {"fund_id": "COF-SP500",   "allocation_pct": 0.70},
            {"fund_id": "COF-STABLE",  "allocation_pct": 0.30},
        ],
    },
]

# Existing loan for PART-009 (Daniela Reyes) — $25k, used for loan cap demo
# IRS cap: $50k - $25k highest balance = $25k remaining; 50% of $100k = $50k → max = $25k
LOANS = [
    {
        "loan_id": "LOAN-0100",
        "participant_id": "PART-009",
        "plan_id": "PLAN-003",
        "loan_type": "general",
        "original_amount": 25000.00,
        "outstanding_balance": 22000.00,
        "highest_balance_last_12_months": 25000.00,
        "interest_rate": 0.0850,           # prime + 2% (Capital One policy)
        "origination_date": "2024-05-01",
        "maturity_date": "2029-05-01",
        "payment_amount": 512.00,
        "payment_frequency": "monthly",
        "status": "active",
    },
]


# ---------------------------------------------------------------------------
# Seed functions
# ---------------------------------------------------------------------------

def seed_plans(cur):
    print("  Seeding plans...")
    for plan in PLANS:
        cur.execute(
            """
            INSERT INTO plans (
                plan_id, plan_name, plan_type, safe_harbor, erisa_plan_number,
                ein, effective_date, plan_year_end,
                eligibility_age, eligibility_months_of_service,
                employer_match, snapshot_version
            ) VALUES (
                %s, %s, %s, %s, %s,
                %s, %s, %s,
                %s, %s,
                %s, %s
            )
            ON CONFLICT (plan_id) DO UPDATE SET
                plan_name = EXCLUDED.plan_name,
                safe_harbor = EXCLUDED.safe_harbor,
                eligibility_age = EXCLUDED.eligibility_age,
                eligibility_months_of_service = EXCLUDED.eligibility_months_of_service,
                employer_match = EXCLUDED.employer_match
            """,
            (
                plan["plan_id"], plan["plan_name"], plan["plan_type"],
                plan["safe_harbor"], plan["erisa_plan_number"],
                plan.get("ein"), plan["effective_date"], plan["plan_year_end"],
                plan["eligibility_age"], plan["eligibility_months_of_service"],
                Json(plan["employer_match"]) if plan.get("employer_match") else None,
                plan["snapshot_version"],
            ),
        )
    print(f"    {len(PLANS)} plans upserted")


def seed_vesting_schedules(cur):
    print("  Seeding vesting schedules...")
    for vs in VESTING_SCHEDULES:
        cur.execute(
            """
            INSERT INTO plan_vesting_schedules (
                plan_id, vesting_type, cliff_years,
                service_crediting_method, is_match_schedule
            ) VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (plan_id, is_match_schedule) DO UPDATE SET
                vesting_type = EXCLUDED.vesting_type,
                cliff_years = EXCLUDED.cliff_years
            """,
            (
                vs["plan_id"], vs["vesting_type"], vs.get("cliff_years"),
                vs["service_crediting_method"], vs["is_match_schedule"],
            ),
        )
    print(f"    {len(VESTING_SCHEDULES)} vesting schedules upserted")


def seed_loan_policies(cur):
    print("  Seeding loan policies...")
    for lp in LOAN_POLICIES:
        cur.execute(
            """
            INSERT INTO plan_loan_policy (
                plan_id, loans_permitted, max_loan_amount, max_loan_pct_of_vested,
                min_loan_amount, max_repayment_years_general, max_repayment_years_primary_res,
                outstanding_loans_permitted, origination_fee, quarterly_maintenance_fee,
                cooldown_days_after_repayment
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (plan_id) DO UPDATE SET
                loans_permitted = EXCLUDED.loans_permitted,
                max_repayment_years_general = EXCLUDED.max_repayment_years_general,
                max_repayment_years_primary_res = EXCLUDED.max_repayment_years_primary_res,
                outstanding_loans_permitted = EXCLUDED.outstanding_loans_permitted,
                origination_fee = EXCLUDED.origination_fee
            """,
            (
                lp["plan_id"], lp["loans_permitted"], lp["max_loan_amount"],
                lp["max_loan_pct_of_vested"], lp["min_loan_amount"],
                lp["max_repayment_years_general"], lp["max_repayment_years_primary_res"],
                lp["outstanding_loans_permitted"], lp["origination_fee"],
                lp["quarterly_maintenance_fee"], lp["cooldown_days_after_repayment"],
            ),
        )
    print(f"    {len(LOAN_POLICIES)} loan policies upserted")


def seed_hardship_policies(cur):
    print("  Seeding hardship policies...")
    for hp in HARDSHIP_POLICIES:
        cur.execute(
            """
            INSERT INTO plan_hardship_policy (
                plan_id, hardship_permitted, hardship_standard,
                qualifying_expenses, six_month_contribution_suspension
            ) VALUES (%s, %s, %s, %s::jsonb, %s)
            ON CONFLICT (plan_id) DO UPDATE SET
                hardship_permitted = EXCLUDED.hardship_permitted,
                qualifying_expenses = EXCLUDED.qualifying_expenses
            """,
            (
                hp["plan_id"], hp["hardship_permitted"], hp["hardship_standard"],
                hp["qualifying_expenses"], hp["six_month_contribution_suspension"],
            ),
        )
    print(f"    {len(HARDSHIP_POLICIES)} hardship policies upserted")


def seed_distribution_options(cur):
    print("  Seeding distribution options...")
    for do_ in DISTRIBUTION_OPTIONS:
        cur.execute(
            """
            INSERT INTO plan_distribution_options (
                plan_id, in_service_age_59_5, normal_retirement_age, early_retirement_age,
                rmd_start_rule, rmd_calculation_method,
                qjsa_survivor_pct, qjsa_waiver_requires_spousal_consent,
                accepts_rollover_in, rollover_in_sources,
                direct_rollover_out_permitted, qdro_procedures_url, qdro_required_fields,
                blackout_is_active, blackout_start_date, blackout_end_date, blackout_reason
            ) VALUES (
                %s, %s, %s, %s,
                %s, %s,
                %s, %s,
                %s, %s::jsonb,
                %s, %s, %s::jsonb,
                %s, %s, %s, %s
            )
            ON CONFLICT (plan_id) DO UPDATE SET
                blackout_is_active = EXCLUDED.blackout_is_active,
                blackout_start_date = EXCLUDED.blackout_start_date,
                blackout_end_date = EXCLUDED.blackout_end_date,
                blackout_reason = EXCLUDED.blackout_reason
            """,
            (
                do_["plan_id"], do_["in_service_age_59_5"],
                do_["normal_retirement_age"], do_.get("early_retirement_age"),
                do_["rmd_start_rule"], do_["rmd_calculation_method"],
                do_["qjsa_survivor_pct"], do_["qjsa_waiver_requires_spousal_consent"],
                do_["accepts_rollover_in"], do_["rollover_in_sources"],
                do_["direct_rollover_out_permitted"], do_.get("qdro_procedures_url"),
                do_["qdro_required_fields"],
                do_["blackout_is_active"], do_.get("blackout_start_date"),
                do_.get("blackout_end_date"), do_.get("blackout_reason"),
            ),
        )
    print(f"    {len(DISTRIBUTION_OPTIONS)} distribution option rows upserted")


def seed_funds(cur):
    print("  Seeding fund lineups...")
    total = 0
    for plan_id, funds in FUND_LINEUPS.items():
        for fund in funds:
            cur.execute(
                """
                INSERT INTO plan_funds (
                    plan_id, fund_id, fund_name, ticker, asset_class,
                    expense_ratio, is_qdia, is_stable_value
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (plan_id, fund_id) DO NOTHING
                """,
                (
                    plan_id, fund["fund_id"], fund["fund_name"],
                    fund.get("ticker"), fund["asset_class"],
                    fund["expense_ratio"], fund["is_qdia"], fund["is_stable_value"],
                ),
            )
            total += 1
    print(f"    {total} fund records inserted")


def seed_agents(cur):
    print("  Seeding agent registry...")
    for agent in AGENTS:
        cur.execute(
            """
            INSERT INTO agent_registry (
                agent_id, agent_name, principal_type,
                allowed_actions, allowed_plan_ids, is_active
            ) VALUES (%s, %s, %s, %s::jsonb, %s::jsonb, %s)
            ON CONFLICT (agent_id) DO UPDATE SET
                allowed_plan_ids = EXCLUDED.allowed_plan_ids,
                is_active = EXCLUDED.is_active
            """,
            (
                agent["agent_id"], agent["agent_name"], agent["principal_type"],
                agent["allowed_actions"], agent["allowed_plan_ids"], agent["is_active"],
            ),
        )
    print(f"    {len(AGENTS)} agents upserted")


def seed_participants(cur):
    print("  Seeding participants...")
    for p in PARTICIPANTS:
        cur.execute(
            """
            INSERT INTO participants (
                participant_id, plan_id, ssn_hash, first_name, last_name,
                date_of_birth, date_of_hire, eligibility_date,
                employment_status, termination_date,
                years_of_vesting_service, hours_of_service_ytd,
                break_in_service, userra_military_leave,
                total_balance, vested_balance, vesting_percentage,
                employee_contributions_ytd, employer_contributions_ytd,
                current_deferral_pct, deferral_type, compensation_ytd,
                is_hce, age_50_or_older, age_60_to_63,
                rmd_required, rmd_amount_current_year, rmd_due_date
            ) VALUES (
                %s, %s, %s, %s, %s,
                %s, %s, %s,
                %s, %s,
                %s, %s,
                %s, %s,
                %s, %s, %s,
                %s, %s,
                %s, %s, %s,
                %s, %s, %s,
                %s, %s, %s
            )
            ON CONFLICT (participant_id) DO UPDATE SET
                first_name = EXCLUDED.first_name,
                last_name = EXCLUDED.last_name,
                plan_id = EXCLUDED.plan_id,
                employment_status = EXCLUDED.employment_status,
                termination_date = EXCLUDED.termination_date,
                years_of_vesting_service = EXCLUDED.years_of_vesting_service,
                hours_of_service_ytd = EXCLUDED.hours_of_service_ytd,
                total_balance = EXCLUDED.total_balance,
                vested_balance = EXCLUDED.vested_balance,
                vesting_percentage = EXCLUDED.vesting_percentage,
                employee_contributions_ytd = EXCLUDED.employee_contributions_ytd,
                employer_contributions_ytd = EXCLUDED.employer_contributions_ytd,
                current_deferral_pct = EXCLUDED.current_deferral_pct,
                deferral_type = EXCLUDED.deferral_type,
                compensation_ytd = EXCLUDED.compensation_ytd,
                is_hce = EXCLUDED.is_hce,
                age_50_or_older = EXCLUDED.age_50_or_older,
                age_60_to_63 = EXCLUDED.age_60_to_63,
                rmd_required = EXCLUDED.rmd_required,
                rmd_amount_current_year = EXCLUDED.rmd_amount_current_year,
                rmd_due_date = EXCLUDED.rmd_due_date,
                updated_at = NOW()
            """,
            (
                p["participant_id"], p["plan_id"], p["ssn_hash"],
                p["first_name"], p["last_name"],
                p["date_of_birth"], p["date_of_hire"], p["eligibility_date"],
                p["employment_status"], p.get("termination_date"),
                p["years_of_vesting_service"], p["hours_of_service_ytd"],
                p["break_in_service"], p["userra_military_leave"],
                p["total_balance"], p["vested_balance"], p["vesting_percentage"],
                p["employee_contributions_ytd"], p["employer_contributions_ytd"],
                p["current_deferral_pct"], p["deferral_type"], p["compensation_ytd"],
                p["is_hce"], p["age_50_or_older"], p["age_60_to_63"],
                p["rmd_required"], p.get("rmd_amount_current_year"), p.get("rmd_due_date"),
            ),
        )
        for election in p.get("elections", []):
            cur.execute(
                """
                INSERT INTO participant_investment_elections (
                    participant_id, plan_id, fund_id, allocation_pct, effective_date
                ) VALUES (%s, %s, %s, %s, CURRENT_DATE)
                ON CONFLICT (participant_id, fund_id, effective_date) DO NOTHING
                """,
                (p["participant_id"], p["plan_id"], election["fund_id"], election["allocation_pct"]),
            )
    print(f"    {len(PARTICIPANTS)} participants upserted")


def seed_loans(cur):
    print("  Seeding loans...")
    for loan in LOANS:
        cur.execute(
            """
            INSERT INTO participant_loans (
                loan_id, participant_id, plan_id, loan_type,
                original_amount, outstanding_balance, highest_balance_last_12_months,
                interest_rate, origination_date, maturity_date,
                payment_amount, payment_frequency, status
            ) VALUES (
                %s, %s, %s, %s,
                %s, %s, %s,
                %s, %s, %s,
                %s, %s, %s
            )
            ON CONFLICT (loan_id) DO NOTHING
            """,
            (
                loan["loan_id"], loan["participant_id"], loan["plan_id"], loan["loan_type"],
                loan["original_amount"], loan["outstanding_balance"], loan["highest_balance_last_12_months"],
                loan["interest_rate"], loan["origination_date"], loan["maturity_date"],
                loan["payment_amount"], loan["payment_frequency"], loan["status"],
            ),
        )
    print(f"    {len(LOANS)} loans inserted")


def delete_removed_data(cur):
    """Remove the old Aldergate demo plans and participants that no longer exist."""
    print("  Removing old demo data (PLAN-001, PLAN-002, PART-001 through PART-005)...")

    old_participants = ["PART-001", "PART-002", "PART-003", "PART-004", "PART-005"]
    old_plans = ["PLAN-001", "PLAN-002"]

    if old_participants:
        cur.execute(
            "DELETE FROM participant_investment_elections WHERE participant_id = ANY(%s)",
            (old_participants,)
        )
        cur.execute(
            "DELETE FROM participant_loans WHERE participant_id = ANY(%s)",
            (old_participants,)
        )
        cur.execute(
            "DELETE FROM participants WHERE participant_id = ANY(%s)",
            (old_participants,)
        )

    if old_plans:
        cur.execute("DELETE FROM plan_funds WHERE plan_id = ANY(%s)", (old_plans,))
        cur.execute("DELETE FROM plan_distribution_options WHERE plan_id = ANY(%s)", (old_plans,))
        cur.execute("DELETE FROM plan_hardship_policy WHERE plan_id = ANY(%s)", (old_plans,))
        cur.execute("DELETE FROM plan_loan_policy WHERE plan_id = ANY(%s)", (old_plans,))
        cur.execute("DELETE FROM plan_vesting_breakpoints WHERE schedule_id IN (SELECT id FROM plan_vesting_schedules WHERE plan_id = ANY(%s))", (old_plans,))
        cur.execute("DELETE FROM plan_vesting_schedules WHERE plan_id = ANY(%s)", (old_plans,))
        cur.execute("DELETE FROM plans WHERE plan_id = ANY(%s)", (old_plans,))

    print("    Done")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print("Aldergate PostgreSQL Seed")
    print("=" * 40)
    conn = connect()
    conn.autocommit = False
    cur = conn.cursor()

    try:
        delete_removed_data(cur)
        seed_plans(cur)
        seed_vesting_schedules(cur)
        seed_loan_policies(cur)
        seed_hardship_policies(cur)
        seed_distribution_options(cur)
        seed_funds(cur)
        seed_agents(cur)
        seed_participants(cur)
        seed_loans(cur)
        conn.commit()
        print()
        print("Seed complete.")
        print()
        print("Plans:")
        print("  PLAN-003  Capital One Financial Corporation Associate Savings Plan")
        print("  PLAN-004  The Prudential Employee Savings Plan (PESP)")
        print()
        print("Participants:")
        print("  PART-006  Gabriel Stone    — PLAN-003  $210k  age 62 / HCE / active employee")
        print("  PART-007  Yuki Tanaka      — PLAN-004   $38k  age 31 / 1.5yr service / cliff not met")
        print("  PART-008  Amara Osei       — PLAN-003   $85k  age 36 / primary demo participant")
        print("  PART-009  Daniela Reyes    — PLAN-003  $100k  age 41 / existing $25k loan")
        print("  PART-010  Eleanor Walsh    — PLAN-003  $400k  age 75 / retired / rmd_required=True")
        print()
        print("Funds:  12 Capital One (Fidelity)  +  9 Prudential PESP (Empower)")
        print("Loans:  LOAN-0100  Daniela Reyes — $25k active  (§72(p) cap demo)")
    except Exception as exc:
        conn.rollback()
        print(f"\nSeed FAILED — rolled back. Error: {exc}", file=sys.stderr)
        raise
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    main()
