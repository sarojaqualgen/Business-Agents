"""
Seed script — loads mock plans and participants into PostgreSQL.
Run once after alembic upgrade head.

    python data/seed.py
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

import json
import hashlib
import psycopg2
import psycopg2.extras
from decimal import Decimal

from data.plans import PLAN_001, PLAN_002
from data.participants import PART_001, PART_002, PART_003, PART_004, PART_005
from data.agents import AGENT_REGISTRY

DATABASE_URL = os.environ["DATABASE_URL"]


def get_conn():
    return psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor)


def seed_plan(cur, plan):
    print(f"  Seeding plan: {plan.plan_id} — {plan.plan_name}")

    employer_match_json = None
    if plan.employer_match:
        employer_match_json = json.dumps({
            "tiers": [t.model_dump() for t in plan.employer_match.tiers],
            "true_up": plan.employer_match.true_up,
        })

    cur.execute("""
        INSERT INTO plans (
            plan_id, plan_name, plan_type, safe_harbor, erisa_plan_number,
            effective_date, plan_year_end, eligibility_age,
            eligibility_months_of_service, employer_match, snapshot_version
        ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        ON CONFLICT (plan_id) DO NOTHING
    """, (
        plan.plan_id, plan.plan_name, plan.plan_type.value,
        plan.safe_harbor, plan.erisa_plan_number, plan.effective_date,
        plan.plan_year_end, plan.eligibility_age,
        plan.eligibility_months_of_service, employer_match_json,
        plan.snapshot_version,
    ))

    # Vesting schedule
    cur.execute("""
        INSERT INTO plan_vesting_schedules
            (plan_id, vesting_type, cliff_years, service_crediting_method, is_match_schedule)
        VALUES (%s,%s,%s,%s,%s)
        ON CONFLICT (plan_id, is_match_schedule) DO NOTHING
        RETURNING id
    """, (
        plan.plan_id,
        plan.match_vesting_schedule.vesting_type.value,
        plan.match_vesting_schedule.cliff_years,
        plan.match_vesting_schedule.service_crediting_method,
        True,
    ))
    row = cur.fetchone()
    if row and plan.match_vesting_schedule.graduated_schedule:
        schedule_id = row["id"]
        for bp in plan.match_vesting_schedule.graduated_schedule:
            cur.execute("""
                INSERT INTO plan_vesting_breakpoints (schedule_id, year, pct)
                VALUES (%s,%s,%s) ON CONFLICT DO NOTHING
            """, (schedule_id, bp.year, bp.pct))

    # Loan policy
    lp = plan.loan_policy
    cur.execute("""
        INSERT INTO plan_loan_policy (
            plan_id, loans_permitted, max_loan_amount, max_loan_pct_of_vested,
            min_loan_amount, max_repayment_years_general, max_repayment_years_primary_res,
            outstanding_loans_permitted, origination_fee, quarterly_maintenance_fee,
            cooldown_days_after_repayment
        ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        ON CONFLICT (plan_id) DO NOTHING
    """, (
        plan.plan_id, lp.loans_permitted, lp.max_loan_amount,
        lp.max_loan_pct_of_vested, lp.min_loan_amount,
        lp.max_repayment_years, lp.primary_residence_extension_years,
        lp.outstanding_loans_permitted, lp.origination_fee,
        lp.quarterly_maintenance_fee, lp.cooldown_days_after_repayment,
    ))

    # Hardship policy
    hp = plan.hardship_policy
    cur.execute("""
        INSERT INTO plan_hardship_policy (
            plan_id, hardship_permitted, hardship_standard,
            qualifying_expenses, six_month_contribution_suspension
        ) VALUES (%s,%s,%s,%s,%s)
        ON CONFLICT (plan_id) DO NOTHING
    """, (
        plan.plan_id, hp.hardship_permitted, hp.hardship_standard.value,
        json.dumps([e.value for e in hp.qualifying_expenses]),
        hp.six_month_contribution_suspension,
    ))

    # Distribution options + rollover + blackout
    do = plan.distribution_options
    rq = plan.rollover_qdro
    bs = plan.blackout_status
    cur.execute("""
        INSERT INTO plan_distribution_options (
            plan_id, in_service_age_59_5, normal_retirement_age, early_retirement_age,
            rmd_start_rule, rmd_calculation_method, qjsa_survivor_pct,
            qjsa_waiver_requires_spousal_consent, accepts_rollover_in,
            rollover_in_sources, direct_rollover_out_permitted,
            qdro_procedures_url, qdro_required_fields,
            blackout_is_active, blackout_start_date, blackout_end_date, blackout_reason
        ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        ON CONFLICT (plan_id) DO NOTHING
    """, (
        plan.plan_id, do.in_service_age_59_5, do.normal_retirement_age,
        do.early_retirement_age, do.rmd_start_rule.value,
        do.rmd_calculation_method.value, do.qjsa_survivor_pct,
        do.qjsa_waiver_requires_spousal_consent, rq.accepts_rollover_in,
        json.dumps(rq.rollover_in_sources), rq.direct_rollover_out_permitted,
        rq.qdro_procedures_url, json.dumps(rq.qdro_required_fields),
        bs.is_active, bs.start_date, bs.end_date, bs.reason,
    ))

    # Fund lineup
    for f in plan.fund_lineup:
        cur.execute("""
            INSERT INTO plan_funds
                (plan_id, fund_id, fund_name, ticker, asset_class, expense_ratio, is_qdia)
            VALUES (%s,%s,%s,%s,%s,%s,%s)
            ON CONFLICT (plan_id, fund_id) DO NOTHING
        """, (
            plan.plan_id, f.fund_id, f.fund_name, f.ticker,
            f.asset_class, f.expense_ratio, f.is_qdia,
        ))


def seed_participant(cur, p):
    print(f"  Seeding participant: {p.participant_id}")

    cur.execute("""
        INSERT INTO participants (
            participant_id, plan_id, ssn_hash, first_name, last_name,
            date_of_birth, date_of_hire, eligibility_date, employment_status,
            years_of_vesting_service, hours_of_service_ytd, break_in_service,
            userra_military_leave, total_balance, vested_balance, vesting_percentage,
            employee_contributions_ytd, employer_contributions_ytd,
            current_deferral_pct, deferral_type, compensation_ytd,
            is_hce, age_50_or_older, age_60_to_63,
            rmd_required, rmd_amount_current_year
        ) VALUES (
            %s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s
        ) ON CONFLICT (participant_id) DO NOTHING
    """, (
        p.participant_id, p.plan_id, p.ssn_hash,
        p.participant_id,  # using ID as placeholder first name (no real PII in mock)
        "Demo",
        p.date_of_birth, p.hire_date, p.eligibility_date,
        p.employment_status.value,
        p.years_of_vesting_service, p.hours_of_service_ytd,
        p.break_in_service, p.userra_military_leave,
        p.total_balance, p.vested_balance, p.vesting_percentage,
        p.employee_contributions_ytd, p.employer_contributions_ytd,
        p.current_deferral_pct, p.deferral_type.value,
        p.compensation_ytd, p.is_hce, p.age_50_or_older, p.age_60_to_63,
        p.rmd_required, p.rmd_amount_current_year,
    ))

    # Outstanding loans
    for loan in p.outstanding_loans:
        cur.execute("""
            INSERT INTO participant_loans (
                loan_id, participant_id, plan_id, loan_type,
                original_amount, outstanding_balance, highest_balance_last_12_months,
                interest_rate, origination_date, maturity_date,
                payment_amount, status
            ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            ON CONFLICT (loan_id) DO NOTHING
        """, (
            loan.loan_id, p.participant_id, p.plan_id, "general",
            loan.principal, loan.outstanding_balance,
            loan.highest_balance_last_12_months,
            loan.interest_rate, loan.origination_date, loan.maturity_date,
            Decimal("500.00"),  # mock payment amount
            "active",
        ))

    # Investment elections
    for election in p.investment_elections:
        cur.execute("""
            INSERT INTO participant_investment_elections
                (participant_id, plan_id, fund_id, allocation_pct, effective_date)
            VALUES (%s,%s,%s,%s, CURRENT_DATE)
            ON CONFLICT (participant_id, fund_id, effective_date) DO NOTHING
        """, (
            p.participant_id, p.plan_id,
            election.fund_id, election.allocation_pct,
        ))


def seed_agents(cur):
    print("  Seeding agent registry...")
    for agent_id, reg in AGENT_REGISTRY.items():
        cur.execute("""
            INSERT INTO agent_registry (
                agent_id, agent_name, principal_type,
                allowed_actions, allowed_plan_ids, is_active
            ) VALUES (%s,%s,%s,%s,%s,%s)
            ON CONFLICT (agent_id) DO NOTHING
        """, (
            agent_id,
            reg.agent_name if hasattr(reg, "agent_name") else agent_id,
            reg.principal_type.value,
            json.dumps([a.value for a in reg.allowed_actions]),
            json.dumps(reg.allowed_plan_ids),
            reg.is_active,
        ))


def main():
    print("\nAldergate — Database Seed")
    print("─" * 40)

    conn = get_conn()
    cur = conn.cursor()

    try:
        print("\nPlans:")
        seed_plan(cur, PLAN_001)
        seed_plan(cur, PLAN_002)

        print("\nParticipants:")
        seed_participant(cur, PART_001)
        seed_participant(cur, PART_002)
        seed_participant(cur, PART_003)
        seed_participant(cur, PART_004)
        seed_participant(cur, PART_005)

        print("\nAgents:")
        seed_agents(cur)

        conn.commit()
        print("\n✓ Seed complete — open TablePlus and check your tables.")

    except Exception as e:
        conn.rollback()
        print(f"\n✗ Error: {e}")
        raise
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    main()
