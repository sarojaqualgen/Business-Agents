"""
Aldergate database layer — PostgreSQL via psycopg2.

All functions return the same Pydantic model types used by the compliance
engine (PlanRecord, ParticipantRecord, etc.) so the FAP rules don't know
whether they're running against a real DB or mock data.

Environment variables required:
    DATABASE_URL  e.g. postgresql://user:password@localhost:5432/aldergate

Connection pool is module-level and initialized on first import.
"""

import hashlib
import json
import os
import uuid
from contextlib import contextmanager
from datetime import date, datetime
from decimal import Decimal

from dotenv import load_dotenv
load_dotenv()
from typing import Optional

import psycopg2
import psycopg2.extras
import psycopg2.pool

from agents.fap.models import FapAuditRecord
from agents.paap.models import (
    InvestmentElection,
    LoanRecord,
    ParticipantRecord,
)
from agents.plap.models import (
    BlackoutStatus,
    DistributionOptions,
    FundRecord,
    HardshipPolicy,
    HardshipStandard,
    LoanPolicy,
    MatchFormula,
    MatchTier,
    PlanCapabilities,
    PlanRecord,
    PlanType,
    QualifyingExpenseType,
    RmdCalculationMethod,
    RmdStartRule,
    RolloverQdroPolicy,
    VestedYearBreakpoint,
    VestingSchedule,
    VestingType,
)

# ---------------------------------------------------------------------------
# Connection pool
# ---------------------------------------------------------------------------

_pool: Optional[psycopg2.pool.ThreadedConnectionPool] = None


def _get_pool() -> psycopg2.pool.ThreadedConnectionPool:
    global _pool
    if _pool is None:
        url = os.environ.get("DATABASE_URL")
        if not url:
            raise RuntimeError(
                "DATABASE_URL environment variable is not set. "
                "Add it to your .env file: DATABASE_URL=postgresql://user:pass@localhost:5432/aldergate"
            )
        _pool = psycopg2.pool.ThreadedConnectionPool(
            minconn=1,
            maxconn=10,
            dsn=url,
            cursor_factory=psycopg2.extras.RealDictCursor,
        )
    return _pool


@contextmanager
def _conn():
    """Context manager: acquire a connection from the pool, commit on success, rollback on error."""
    pool = _get_pool()
    conn = pool.getconn()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        pool.putconn(conn)


# ---------------------------------------------------------------------------
# Plan queries — PLAP data layer
# ---------------------------------------------------------------------------

def get_plan(plan_id: str) -> Optional[PlanRecord]:
    """Fetch a fully-assembled PlanRecord from the database."""
    with _conn() as conn:
        cur = conn.cursor()

        cur.execute("SELECT * FROM plans WHERE plan_id = %s", (plan_id,))
        row = cur.fetchone()
        if row is None:
            return None

        # Match vesting schedule
        cur.execute(
            "SELECT * FROM plan_vesting_schedules WHERE plan_id = %s AND is_match_schedule = TRUE",
            (plan_id,),
        )
        vs_row = cur.fetchone()
        if vs_row is None:
            return None

        breakpoints = []
        if vs_row["vesting_type"] == "graduated":
            cur.execute(
                "SELECT year, pct FROM plan_vesting_breakpoints WHERE schedule_id = %s ORDER BY year",
                (vs_row["id"],),
            )
            breakpoints = [VestedYearBreakpoint(year=r["year"], pct=float(r["pct"])) for r in cur.fetchall()]

        vesting_schedule = VestingSchedule(
            vesting_type=VestingType(vs_row["vesting_type"]),
            cliff_years=vs_row["cliff_years"],
            graduated_schedule=breakpoints if breakpoints else None,
            service_crediting_method=vs_row["service_crediting_method"],
        )

        # Loan policy
        cur.execute("SELECT * FROM plan_loan_policy WHERE plan_id = %s", (plan_id,))
        lp_row = cur.fetchone()
        loan_policy = LoanPolicy(
            loans_permitted=lp_row["loans_permitted"],
            max_loan_amount=lp_row["max_loan_amount"],
            max_loan_pct_of_vested=float(lp_row["max_loan_pct_of_vested"]),
            min_loan_amount=lp_row["min_loan_amount"],
            max_repayment_years=lp_row["max_repayment_years_general"],
            primary_residence_extension_years=lp_row["max_repayment_years_primary_res"],
            outstanding_loans_permitted=lp_row["outstanding_loans_permitted"],
            origination_fee=Decimal(str(lp_row["origination_fee"])),
            quarterly_maintenance_fee=Decimal(str(lp_row["quarterly_maintenance_fee"])),
            cooldown_days_after_repayment=lp_row["cooldown_days_after_repayment"],
        ) if lp_row else LoanPolicy(loans_permitted=False)

        # Hardship policy
        cur.execute("SELECT * FROM plan_hardship_policy WHERE plan_id = %s", (plan_id,))
        hp_row = cur.fetchone()
        def _expense(e: str) -> QualifyingExpenseType:
            try:
                return QualifyingExpenseType(e)   # match by value
            except ValueError:
                return QualifyingExpenseType[e]   # match by name (e.g. "fema_disaster" → "FEMA_disaster")

        hardship_policy = HardshipPolicy(
            hardship_permitted=hp_row["hardship_permitted"],
            hardship_standard=HardshipStandard(hp_row["hardship_standard"]),
            qualifying_expenses=[_expense(e) for e in (hp_row["qualifying_expenses"] or [])],
            six_month_contribution_suspension=hp_row["six_month_contribution_suspension"],
        ) if hp_row else HardshipPolicy(hardship_permitted=False)

        # Distribution options + rollover/QDRO + blackout
        cur.execute("SELECT * FROM plan_distribution_options WHERE plan_id = %s", (plan_id,))
        do_row = cur.fetchone()
        if do_row:
            distribution_options = DistributionOptions(
                in_service_age_59_5=do_row["in_service_age_59_5"],
                normal_retirement_age=do_row["normal_retirement_age"],
                early_retirement_age=do_row["early_retirement_age"],
                rmd_start_rule=RmdStartRule(do_row["rmd_start_rule"]),
                rmd_calculation_method=RmdCalculationMethod(do_row["rmd_calculation_method"]),
                qjsa_survivor_pct=float(do_row["qjsa_survivor_pct"]),
                qjsa_waiver_requires_spousal_consent=do_row["qjsa_waiver_requires_spousal_consent"],
            )
            rollover_qdro = RolloverQdroPolicy(
                accepts_rollover_in=do_row["accepts_rollover_in"],
                rollover_in_sources=do_row["rollover_in_sources"] or [],
                direct_rollover_out_permitted=do_row["direct_rollover_out_permitted"],
                qdro_procedures_url=do_row["qdro_procedures_url"],
                qdro_required_fields=do_row["qdro_required_fields"] or [],
            )
            blackout_status = BlackoutStatus(
                is_active=do_row["blackout_is_active"],
                start_date=str(do_row["blackout_start_date"]) if do_row["blackout_start_date"] else None,
                end_date=str(do_row["blackout_end_date"]) if do_row["blackout_end_date"] else None,
                reason=do_row["blackout_reason"],
            )
        else:
            distribution_options = DistributionOptions()
            rollover_qdro = RolloverQdroPolicy()
            blackout_status = BlackoutStatus(is_active=False)

        # Fund lineup
        cur.execute(
            "SELECT * FROM plan_funds WHERE plan_id = %s AND (available_to IS NULL OR available_to >= CURRENT_DATE) ORDER BY fund_name",
            (plan_id,),
        )
        fund_lineup = [
            FundRecord(
                fund_id=f["fund_id"],
                fund_name=f["fund_name"],
                ticker=f["ticker"],
                asset_class=f["asset_class"],
                expense_ratio=float(f["expense_ratio"]),
                is_qdia=f["is_qdia"],
            )
            for f in cur.fetchall()
        ]

        # Employer match
        employer_match = None
        if row["employer_match"]:
            match_data = row["employer_match"] if isinstance(row["employer_match"], dict) else json.loads(row["employer_match"])
            employer_match = MatchFormula(
                tiers=[MatchTier(**t) for t in match_data.get("tiers", [])],
                true_up=match_data.get("true_up", False),
            )

        return PlanRecord(
            plan_id=row["plan_id"],
            plan_name=row["plan_name"],
            plan_type=PlanType(row["plan_type"]),
            safe_harbor=row["safe_harbor"],
            erisa_plan_number=row["erisa_plan_number"],
            effective_date=str(row["effective_date"]),
            plan_year_end=row["plan_year_end"],
            eligibility_age=row["eligibility_age"],
            eligibility_months_of_service=row["eligibility_months_of_service"],
            employer_match=employer_match,
            match_vesting_schedule=vesting_schedule,
            loan_policy=loan_policy,
            hardship_policy=hardship_policy,
            distribution_options=distribution_options,
            rollover_qdro=rollover_qdro,
            blackout_status=blackout_status,
            fund_lineup=fund_lineup,
            snapshot_version=row["snapshot_version"],
        )


def get_capabilities(plan_id: str) -> Optional[PlanCapabilities]:
    plan = get_plan(plan_id)
    if not plan:
        return None
    return PlanCapabilities(
        plan_id=plan_id,
        capabilities={
            "loan_initiation": plan.loan_policy.loans_permitted,
            "hardship_distribution": plan.hardship_policy.hardship_permitted,
            "in_service_distribution": plan.distribution_options.in_service_age_59_5,
            "direct_rollover_out": plan.rollover_qdro.direct_rollover_out_permitted,
            "qdro_processing": True,
            "rmd_scheduling": True,
        },
    )


# ---------------------------------------------------------------------------
# Participant queries — PAAP data layer
# ---------------------------------------------------------------------------

def get_participant(participant_id: str) -> Optional[ParticipantRecord]:
    """Fetch a fully-assembled ParticipantRecord from the database."""
    with _conn() as conn:
        cur = conn.cursor()

        cur.execute("SELECT * FROM participants WHERE participant_id = %s", (participant_id,))
        row = cur.fetchone()
        if row is None:
            return None

        # Outstanding loans
        cur.execute(
            """
            SELECT loan_id, original_amount, outstanding_balance, highest_balance_last_12_months,
                   interest_rate, origination_date, maturity_date
            FROM participant_loans
            WHERE participant_id = %s AND status = 'active'
            """,
            (participant_id,),
        )
        outstanding_loans = [
            LoanRecord(
                loan_id=l["loan_id"],
                principal=Decimal(str(l["original_amount"])),
                outstanding_balance=Decimal(str(l["outstanding_balance"])),
                interest_rate=float(l["interest_rate"]),
                origination_date=str(l["origination_date"]),
                maturity_date=str(l["maturity_date"]),
                highest_balance_last_12_months=Decimal(str(l["highest_balance_last_12_months"])),
            )
            for l in cur.fetchall()
        ]

        # Investment elections (most recent per fund)
        cur.execute(
            """
            SELECT DISTINCT ON (fund_id) fund_id, allocation_pct
            FROM participant_investment_elections
            WHERE participant_id = %s
            ORDER BY fund_id, effective_date DESC
            """,
            (participant_id,),
        )
        investment_elections = [
            InvestmentElection(fund_id=e["fund_id"], allocation_pct=float(e["allocation_pct"]))
            for e in cur.fetchall()
        ]

        # DOB stored as DATE in DB — format as string for the model
        dob = row["date_of_birth"]
        dob_str = dob.strftime("%Y-%m-%d") if isinstance(dob, date) else str(dob)

        return ParticipantRecord(
            participant_id=row["participant_id"],
            plan_id=row["plan_id"],
            ssn_hash=row["ssn_hash"],
            date_of_birth=dob_str,
            hire_date=str(row["date_of_hire"]),
            eligibility_date=str(row["eligibility_date"]),
            employment_status=row["employment_status"],
            termination_date=str(row["termination_date"]) if row["termination_date"] else None,
            hours_of_service_ytd=row["hours_of_service_ytd"],
            years_of_vesting_service=float(row["years_of_vesting_service"]),
            break_in_service=row["break_in_service"],
            userra_military_leave=row["userra_military_leave"],
            vested_balance=Decimal(str(row["vested_balance"])),
            total_balance=Decimal(str(row["total_balance"])),
            vesting_percentage=float(row["vesting_percentage"]),
            employee_contributions_ytd=Decimal(str(row["employee_contributions_ytd"])),
            employer_contributions_ytd=Decimal(str(row["employer_contributions_ytd"])),
            investment_elections=investment_elections,
            current_deferral_pct=float(row["current_deferral_pct"]),
            deferral_type=row["deferral_type"],
            outstanding_loans=outstanding_loans,
            rmd_required=row["rmd_required"],
            rmd_amount_current_year=Decimal(str(row["rmd_amount_current_year"])) if row["rmd_amount_current_year"] else None,
            rmd_due_date=str(row["rmd_due_date"]) if row["rmd_due_date"] else None,
            is_hce=row["is_hce"],
            compensation_ytd=Decimal(str(row["compensation_ytd"])),
            age_50_or_older=row["age_50_or_older"],
            age_60_to_63=row["age_60_to_63"],
        )


# ---------------------------------------------------------------------------
# FAP token operations
# ---------------------------------------------------------------------------

def write_token(
    token_id: str,
    expires_at: datetime,
    agent_id: str,
    participant_id: Optional[str],
    plan_id: Optional[str],
    action: str,
    payload_hash: str,
    audit_id: Optional[str] = None,
) -> None:
    with _conn() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO fap_tokens (token_id, expires_at, agent_id, participant_id, plan_id, action, payload_hash, audit_id)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (token_id, expires_at, agent_id, participant_id, plan_id, action, payload_hash, audit_id),
        )


def is_token_consumed(token_id: str) -> bool:
    with _conn() as conn:
        cur = conn.cursor()
        cur.execute("SELECT consumed FROM fap_tokens WHERE token_id = %s", (token_id,))
        row = cur.fetchone()
        if row is None:
            return True  # Unknown token = treat as consumed
        return row["consumed"]


def consume_token(token_id: str) -> bool:
    """Mark token as consumed. Returns False if already consumed (double-spend attempt)."""
    with _conn() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            UPDATE fap_tokens
            SET consumed = TRUE, consumed_at = NOW()
            WHERE token_id = %s AND consumed = FALSE AND expires_at > NOW()
            """,
            (token_id,),
        )
        return cur.rowcount == 1


# ---------------------------------------------------------------------------
# FAP audit log — append-only
# ---------------------------------------------------------------------------

def write_audit_record(record: FapAuditRecord) -> None:
    outcome = "approved" if record.authorized else "denied"
    principal_type = record.principal_type.value if hasattr(record.principal_type, "value") else record.principal_type
    autonomy_level = record.autonomy_level.value if record.autonomy_level and hasattr(record.autonomy_level, "value") else record.autonomy_level
    denial_code = record.denial_code.value if record.denial_code and hasattr(record.denial_code, "value") else record.denial_code

    with _conn() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO fap_audit_log (
                audit_id, created_at, agent_id, principal_type, participant_id, plan_id,
                action, payload_hash, outcome, autonomy_level, denial_code, erisa_citation,
                master_ref_section, token_id
            ) VALUES (
                %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s,
                %s, %s
            )
            """,
            (
                record.audit_id,
                record.timestamp,
                record.agent_id,
                principal_type,
                record.participant_id,
                record.plan_id,
                record.action,
                "",        # payload_hash — FapAuditRecord intentionally omits payload (may contain PII)
                outcome,
                autonomy_level,
                denial_code,
                record.erisa_citation,
                record.master_ref_section,
                record.token_id,
            ),
        )


# ---------------------------------------------------------------------------
# Plan admin CRUD — used by the admin dashboard (Option A ingestion)
# ---------------------------------------------------------------------------

def create_plan(plan: PlanRecord) -> str:
    """
    Insert a new plan and all its sub-records. Returns plan_id.
    Called by the admin dashboard when a plan sponsor onboards a new plan.
    """
    with _conn() as conn:
        cur = conn.cursor()

        # Core plan record
        employer_match_json = None
        if plan.employer_match:
            employer_match_json = json.dumps({
                "tiers": [t.model_dump() for t in plan.employer_match.tiers],
                "true_up": plan.employer_match.true_up,
            })

        cur.execute(
            """
            INSERT INTO plans (
                plan_id, plan_name, plan_type, safe_harbor, erisa_plan_number,
                effective_date, plan_year_end, eligibility_age, eligibility_months_of_service,
                employer_match, snapshot_version
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                plan.plan_id, plan.plan_name, plan.plan_type.value, plan.safe_harbor,
                plan.erisa_plan_number, plan.effective_date, plan.plan_year_end,
                plan.eligibility_age, plan.eligibility_months_of_service,
                employer_match_json, plan.snapshot_version,
            ),
        )

        # Vesting schedule
        cur.execute(
            """
            INSERT INTO plan_vesting_schedules (plan_id, vesting_type, cliff_years, service_crediting_method, is_match_schedule)
            VALUES (%s, %s, %s, %s, %s) RETURNING id
            """,
            (
                plan.plan_id,
                plan.match_vesting_schedule.vesting_type.value,
                plan.match_vesting_schedule.cliff_years,
                plan.match_vesting_schedule.service_crediting_method,
                True,
            ),
        )
        schedule_id = cur.fetchone()["id"]

        if plan.match_vesting_schedule.graduated_schedule:
            psycopg2.extras.execute_values(
                cur,
                "INSERT INTO plan_vesting_breakpoints (schedule_id, year, pct) VALUES %s",
                [(schedule_id, bp.year, bp.pct) for bp in plan.match_vesting_schedule.graduated_schedule],
            )

        # Loan policy
        lp = plan.loan_policy
        cur.execute(
            """
            INSERT INTO plan_loan_policy (
                plan_id, loans_permitted, max_loan_amount, max_loan_pct_of_vested,
                min_loan_amount, max_repayment_years_general, max_repayment_years_primary_res,
                outstanding_loans_permitted, origination_fee, quarterly_maintenance_fee,
                cooldown_days_after_repayment
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                plan.plan_id, lp.loans_permitted, lp.max_loan_amount, lp.max_loan_pct_of_vested,
                lp.min_loan_amount, lp.max_repayment_years, lp.primary_residence_extension_years,
                lp.outstanding_loans_permitted, lp.origination_fee, lp.quarterly_maintenance_fee,
                lp.cooldown_days_after_repayment,
            ),
        )

        # Hardship policy
        hp = plan.hardship_policy
        cur.execute(
            """
            INSERT INTO plan_hardship_policy (
                plan_id, hardship_permitted, hardship_standard, qualifying_expenses,
                six_month_contribution_suspension
            ) VALUES (%s, %s, %s, %s, %s)
            """,
            (
                plan.plan_id, hp.hardship_permitted, hp.hardship_standard.value,
                json.dumps([e.value for e in hp.qualifying_expenses]),
                hp.six_month_contribution_suspension,
            ),
        )

        # Distribution options
        do = plan.distribution_options
        rq = plan.rollover_qdro
        bs = plan.blackout_status
        cur.execute(
            """
            INSERT INTO plan_distribution_options (
                plan_id, in_service_age_59_5, normal_retirement_age, early_retirement_age,
                rmd_start_rule, rmd_calculation_method, qjsa_survivor_pct,
                qjsa_waiver_requires_spousal_consent, accepts_rollover_in, rollover_in_sources,
                direct_rollover_out_permitted, qdro_procedures_url, qdro_required_fields,
                blackout_is_active, blackout_start_date, blackout_end_date, blackout_reason
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                plan.plan_id, do.in_service_age_59_5, do.normal_retirement_age, do.early_retirement_age,
                do.rmd_start_rule.value, do.rmd_calculation_method.value, do.qjsa_survivor_pct,
                do.qjsa_waiver_requires_spousal_consent, rq.accepts_rollover_in,
                json.dumps(rq.rollover_in_sources), rq.direct_rollover_out_permitted,
                rq.qdro_procedures_url, json.dumps(rq.qdro_required_fields),
                bs.is_active, bs.start_date, bs.end_date, bs.reason,
            ),
        )

        # Fund lineup
        if plan.fund_lineup:
            psycopg2.extras.execute_values(
                cur,
                """
                INSERT INTO plan_funds (plan_id, fund_id, fund_name, ticker, asset_class, expense_ratio, is_qdia)
                VALUES %s
                """,
                [
                    (plan.plan_id, f.fund_id, f.fund_name, f.ticker, f.asset_class, f.expense_ratio, f.is_qdia)
                    for f in plan.fund_lineup
                ],
            )

    return plan.plan_id


def update_blackout_status(plan_id: str, is_active: bool, start_date=None, end_date=None, reason=None) -> None:
    """Update blackout status without touching other plan configuration."""
    with _conn() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            UPDATE plan_distribution_options
            SET blackout_is_active = %s, blackout_start_date = %s, blackout_end_date = %s,
                blackout_reason = %s, updated_at = NOW()
            WHERE plan_id = %s
            """,
            (is_active, start_date, end_date, reason, plan_id),
        )


# ---------------------------------------------------------------------------
# Utility
# ---------------------------------------------------------------------------

def get_conn():
    """Return a raw psycopg2 connection (for scripts that manage their own transactions)."""
    import psycopg2.extras as _extras
    url = os.environ.get("DATABASE_URL", "postgresql://devanshsaroja@localhost:5432/aldergate")
    return psycopg2.connect(url, cursor_factory=_extras.RealDictCursor)


def all_plan_ids() -> list[str]:
    with _conn() as conn:
        cur = conn.cursor()
        cur.execute("SELECT plan_id FROM plans ORDER BY plan_id")
        return [r["plan_id"] for r in cur.fetchall()]


def all_participant_ids() -> list[str]:
    with _conn() as conn:
        cur = conn.cursor()
        cur.execute("SELECT participant_id FROM participants ORDER BY participant_id")
        return [r["participant_id"] for r in cur.fetchall()]


def hash_ssn(ssn: str) -> str:
    """One-way hash for SSN storage. Never store raw SSN."""
    cleaned = ssn.replace("-", "").replace(" ", "")
    return hashlib.sha256(cleaned.encode()).hexdigest()


def _db_ok() -> bool:
    """True if DATABASE_URL is set and the pool can be obtained."""
    try:
        _get_pool()
        return True
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Phase 6 — transactions
# ---------------------------------------------------------------------------

def record_transaction(
    participant_id: str,
    plan_id: str,
    action: str,
    amount: Optional[Decimal] = None,
    payload: Optional[dict] = None,
    fap_token_id: Optional[str] = None,
    autonomy_level: Optional[str] = None,
    queue_entry_id: Optional[str] = None,
) -> str:
    """Insert a transaction record after execution. Returns transaction_id UUID."""
    transaction_id = str(uuid.uuid4())
    with _conn() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO transactions
                (transaction_id, participant_id, plan_id, action, amount, payload,
                 fap_token_id, autonomy_level, queue_entry_id)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (transaction_id, participant_id, plan_id, action, amount,
             json.dumps(payload) if payload else None,
             fap_token_id, autonomy_level, queue_entry_id),
        )
    return transaction_id


def decrement_vested_balance(participant_id: str, amount: Decimal) -> None:
    """Reduce vested_balance after a disbursement. Clamped to 0."""
    with _conn() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            UPDATE participants
            SET vested_balance = GREATEST(vested_balance - %s, 0)
            WHERE participant_id = %s
            """,
            (amount, participant_id),
        )


def create_loan_record(
    participant_id: str,
    plan_id: str,
    amount: Decimal,
    repayment_years: int,
    interest_rate: Decimal = Decimal("0.085"),
) -> str:
    """Insert a new loan into participant_loans after loan_initiation disburse.
    Returns loan_id. Interest rate defaults to 8.5% — recordkeeper sets actual rate in Phase 5."""
    from datetime import date as _date
    loan_id = f"LOAN-{str(uuid.uuid4())[:6].upper()}"
    today = _date.today()
    maturity = _date(today.year + repayment_years, today.month, today.day)
    n = repayment_years * 12
    r = float(interest_rate) / 12
    payment = float(amount) * (r * (1 + r) ** n) / ((1 + r) ** n - 1) if r > 0 else float(amount) / n
    with _conn() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO participant_loans
                (loan_id, participant_id, plan_id, loan_type,
                 original_amount, outstanding_balance, highest_balance_last_12_months,
                 interest_rate, origination_date, maturity_date,
                 payment_amount, payment_frequency, status)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (loan_id, participant_id, plan_id, "general",
             amount, amount, amount,
             interest_rate, today, maturity,
             Decimal(str(round(payment, 2))), "monthly", "active"),
        )
    return loan_id


# ---------------------------------------------------------------------------
# Phase 6 — review queue
# ---------------------------------------------------------------------------

def write_review_queue_entry(
    entry_id: str,
    participant_id: str,
    plan_id: str,
    agent_id: str,
    principal_type: str,
    action: str,
    payload: dict,
    fap_audit_id: str,
    fap_token: str,
    created_at: str,
) -> None:
    with _conn() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO review_queue
                (entry_id, participant_id, plan_id, agent_id, principal_type,
                 action, payload, fap_audit_id, fap_token, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (entry_id, participant_id, plan_id, agent_id, principal_type,
             action, json.dumps(payload), fap_audit_id, fap_token, created_at),
        )


def get_review_queue_entry(entry_id: str) -> Optional[dict]:
    with _conn() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM review_queue WHERE entry_id = %s", (entry_id,))
        row = cur.fetchone()
        return dict(row) if row else None


def get_review_queue_pending(plan_id: Optional[str] = None) -> list[dict]:
    with _conn() as conn:
        cur = conn.cursor()
        if plan_id:
            cur.execute(
                "SELECT * FROM review_queue WHERE status = 'pending' AND plan_id = %s ORDER BY created_at",
                (plan_id,),
            )
        else:
            cur.execute("SELECT * FROM review_queue WHERE status = 'pending' ORDER BY created_at")
        return [dict(r) for r in cur.fetchall()]


def get_all_review_queue(plan_id: Optional[str] = None) -> list[dict]:
    with _conn() as conn:
        cur = conn.cursor()
        if plan_id:
            cur.execute(
                "SELECT * FROM review_queue WHERE plan_id = %s ORDER BY created_at DESC",
                (plan_id,),
            )
        else:
            cur.execute("SELECT * FROM review_queue ORDER BY created_at DESC")
        return [dict(r) for r in cur.fetchall()]


def update_review_queue_status(
    entry_id: str,
    new_status: str,
    sponsor_note: str = "",
    resolved_at: Optional[str] = None,
    match_status: Optional[str] = None,
) -> bool:
    """Update queue entry status. If match_status is set, only updates if current status matches."""
    with _conn() as conn:
        cur = conn.cursor()
        if match_status:
            cur.execute(
                """
                UPDATE review_queue
                SET status = %s, sponsor_note = %s, resolved_at = %s
                WHERE entry_id = %s AND status = %s
                """,
                (new_status, sponsor_note, resolved_at, entry_id, match_status),
            )
        else:
            cur.execute(
                "UPDATE review_queue SET status = %s, sponsor_note = %s, resolved_at = %s WHERE entry_id = %s",
                (new_status, sponsor_note, resolved_at, entry_id),
            )
        return cur.rowcount == 1


def update_review_queue_token(entry_id: str, new_fap_token: str) -> bool:
    """Replace the stored FAP token (used for re-issue on sponsor approval)."""
    with _conn() as conn:
        cur = conn.cursor()
        cur.execute(
            "UPDATE review_queue SET fap_token = %s WHERE entry_id = %s",
            (new_fap_token, entry_id),
        )
        return cur.rowcount == 1


# ---------------------------------------------------------------------------
# Phase 6 — documents
# ---------------------------------------------------------------------------

def write_document_record(
    doc_id: str,
    participant_id: str,
    plan_id: str,
    queue_entry_id: str,
    action_type: str,
    expense_type: str,
    doc_type: str,
    filename: str,
    content_preview: str,
    object_key: str,
    uploaded_at: str,
) -> None:
    with _conn() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO documents
                (doc_id, participant_id, plan_id, queue_entry_id, action_type,
                 expense_type, doc_type, filename, content_preview, object_key, uploaded_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (doc_id, participant_id, plan_id, queue_entry_id, action_type,
             expense_type, doc_type, filename, content_preview, object_key, uploaded_at),
        )


def get_documents_by_entry(queue_entry_id: str) -> list[dict]:
    with _conn() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT * FROM documents WHERE queue_entry_id = %s ORDER BY uploaded_at",
            (queue_entry_id,),
        )
        return [dict(r) for r in cur.fetchall()]


def get_documents_by_participant(participant_id: str) -> list[dict]:
    with _conn() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT * FROM documents WHERE participant_id = %s ORDER BY uploaded_at DESC",
            (participant_id,),
        )
        return [dict(r) for r in cur.fetchall()]


def mark_document_verified_db(doc_id: str, verified: bool, note: str, verified_at: str) -> bool:
    with _conn() as conn:
        cur = conn.cursor()
        cur.execute(
            "UPDATE documents SET verified = %s, verification_note = %s, verified_at = %s WHERE doc_id = %s",
            (verified, note, verified_at, doc_id),
        )
        return cur.rowcount == 1


def approve_document_by_sponsor_db(entry_id: str, note: str, approved_at: str) -> int:
    with _conn() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            UPDATE documents
            SET sponsor_doc_approved = TRUE, sponsor_doc_note = %s, sponsor_doc_approved_at = %s
            WHERE queue_entry_id = %s
            """,
            (note, approved_at, entry_id),
        )
        return cur.rowcount


# ---------------------------------------------------------------------------
# Phase 6 — token unconsume (saga rollback compensation)
# ---------------------------------------------------------------------------

def unconsume_token_db(token_id: str) -> None:
    """Reverse a token consumption — saga rollback when execution fails after token was consumed."""
    with _conn() as conn:
        cur = conn.cursor()
        cur.execute(
            "UPDATE fap_tokens SET consumed = FALSE, consumed_at = NULL WHERE token_id = %s",
            (token_id,),
        )


# ---------------------------------------------------------------------------
# Phase 6 — audit log reads
# ---------------------------------------------------------------------------

def get_all_audit_records_db(limit: int = 500) -> list[dict]:
    with _conn() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT * FROM fap_audit_log ORDER BY created_at DESC LIMIT %s",
            (limit,),
        )
        return [dict(r) for r in cur.fetchall()]


def get_audit_record_db(audit_id: str) -> Optional[dict]:
    with _conn() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM fap_audit_log WHERE audit_id = %s", (audit_id,))
        row = cur.fetchone()
        return dict(row) if row else None
