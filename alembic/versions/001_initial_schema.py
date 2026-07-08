"""
Initial schema — creates all Aldergate tables.

Revision:  001
Date:      2026-06-26
"""

revision = "001"
down_revision = None
branch_labels = None
depends_on = None

import os
import re

from alembic import op


def upgrade() -> None:
    schema_path = os.path.join(os.path.dirname(__file__), "..", "..", "data", "schema.sql")
    with open(schema_path, "r") as f:
        sql = f.read()

    # Strip all -- comments (including those with semicolons inside them) before splitting
    sql_no_comments = re.sub(r"--[^\n]*", "", sql)
    statements = [s.strip() for s in sql_no_comments.split(";") if s.strip()]
    for stmt in statements:
        op.execute(stmt)


def downgrade() -> None:
    tables = [
        "fap_audit_log",
        "fap_tokens",
        "agent_registry",
        "participant_investment_elections",
        "participant_loans",
        "participants",
        "plan_funds",
        "plan_distribution_options",
        "plan_hardship_policy",
        "plan_loan_policy",
        "plan_vesting_breakpoints",
        "plan_vesting_schedules",
        "plans",
    ]
    for table in tables:
        op.execute(f"DROP TABLE IF EXISTS {table} CASCADE")
