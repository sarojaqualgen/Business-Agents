"""Phase 6 — transactions, review_queue, and documents tables.

Revision ID: 002
Revises: 001
"""

revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None

from alembic import op


_UP = """
CREATE TABLE IF NOT EXISTS transactions (
    transaction_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    participant_id VARCHAR(32) REFERENCES participants(participant_id),
    plan_id        VARCHAR(32) REFERENCES plans(plan_id),
    action         VARCHAR(64) NOT NULL,
    amount         DECIMAL(12,2),
    payload        JSONB,
    fap_token_id   VARCHAR(64),
    autonomy_level VARCHAR(16),
    queue_entry_id VARCHAR(8),
    executed_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_transactions_participant ON transactions(participant_id);
CREATE INDEX IF NOT EXISTS idx_transactions_executed_at ON transactions(executed_at DESC);

CREATE TABLE IF NOT EXISTS review_queue (
    entry_id       VARCHAR(8)  PRIMARY KEY,
    participant_id VARCHAR(32) REFERENCES participants(participant_id),
    plan_id        VARCHAR(32) REFERENCES plans(plan_id),
    agent_id       VARCHAR(64),
    principal_type VARCHAR(32),
    action         VARCHAR(64) NOT NULL,
    payload        JSONB,
    fap_audit_id   VARCHAR(64),
    fap_token      TEXT,
    status         VARCHAR(32) NOT NULL DEFAULT 'pending'
                   CHECK (status IN ('pending','approved','denied','approved_awaiting_bank_details')),
    sponsor_note   TEXT DEFAULT '',
    created_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    resolved_at    TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_review_queue_status ON review_queue(status);
CREATE INDEX IF NOT EXISTS idx_review_queue_plan   ON review_queue(plan_id, status);

CREATE TABLE IF NOT EXISTS documents (
    doc_id                VARCHAR(8)   PRIMARY KEY,
    participant_id        VARCHAR(32)  REFERENCES participants(participant_id),
    plan_id               VARCHAR(32),
    queue_entry_id        VARCHAR(8)   REFERENCES review_queue(entry_id) ON DELETE CASCADE,
    action_type           VARCHAR(64),
    expense_type          VARCHAR(64),
    doc_type              VARCHAR(64),
    filename              VARCHAR(256),
    content_preview       TEXT DEFAULT '',
    object_key            VARCHAR(512) DEFAULT '',
    uploaded_at           TIMESTAMPTZ NOT NULL,
    verified              BOOLEAN DEFAULT FALSE,
    verification_note     TEXT DEFAULT '',
    verified_at           TIMESTAMPTZ,
    sponsor_doc_approved  BOOLEAN DEFAULT FALSE,
    sponsor_doc_note      TEXT DEFAULT '',
    sponsor_doc_approved_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_documents_entry ON documents(queue_entry_id);
CREATE INDEX IF NOT EXISTS idx_documents_participant ON documents(participant_id);
"""

_DOWN = """
DROP TABLE IF EXISTS documents CASCADE;
DROP TABLE IF EXISTS review_queue CASCADE;
DROP TABLE IF EXISTS transactions CASCADE;
"""


def upgrade() -> None:
    for stmt in _UP.strip().split(";"):
        stmt = stmt.strip()
        if stmt:
            op.execute(stmt)


def downgrade() -> None:
    for stmt in _DOWN.strip().split(";"):
        stmt = stmt.strip()
        if stmt:
            op.execute(stmt)
