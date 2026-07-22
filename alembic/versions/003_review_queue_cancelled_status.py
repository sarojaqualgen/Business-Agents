"""Add 'cancelled' to review_queue status CHECK constraint.

The original constraint only allowed: pending, approved, denied, approved_awaiting_bank_details.
Participant-initiated cancellations (after document rejection) require 'cancelled' status.

Revision ID: 003
Revises: 002
"""

revision = "003"
down_revision = "002"
branch_labels = None
depends_on = None

from alembic import op


_UP = """
ALTER TABLE review_queue
    DROP CONSTRAINT IF EXISTS review_queue_status_check;

ALTER TABLE review_queue
    ADD CONSTRAINT review_queue_status_check
    CHECK (status IN ('pending','approved','denied','approved_awaiting_bank_details','cancelled'));
"""

_DOWN = """
-- Revert: any 'cancelled' rows must be deleted or updated first, or this will fail.
UPDATE review_queue SET status = 'denied' WHERE status = 'cancelled';

ALTER TABLE review_queue
    DROP CONSTRAINT IF EXISTS review_queue_status_check;

ALTER TABLE review_queue
    ADD CONSTRAINT review_queue_status_check
    CHECK (status IN ('pending','approved','denied','approved_awaiting_bank_details'));
"""


def upgrade():
    op.execute(_UP)


def downgrade():
    op.execute(_DOWN)
