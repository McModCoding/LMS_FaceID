"""Idempotent exam behavior event log."""

import sqlalchemy as sa

from alembic import op

revision = "0016_m6_exam_events"
down_revision = "0015_m5a_materials"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "exam_events",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("attempt_id", sa.BigInteger(), sa.ForeignKey("exam_attempts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("event_id", sa.String(36), nullable=False),
        sa.Column("type", sa.String(32), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("counted", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("meta", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.UniqueConstraint("attempt_id", "event_id", name="uq_exam_event_request"),
    )
    op.create_index("ix_exam_events_attempt_id", "exam_events", ["attempt_id"])


def downgrade():
    op.drop_table("exam_events")
