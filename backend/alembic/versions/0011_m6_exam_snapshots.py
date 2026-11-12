"""Prepare immutable exam content snapshots.

Revision ID: 0011_m6_exam_snapshots
Revises: 0010_m6_exam_drafts
"""

import sqlalchemy as sa

from alembic import op

revision = "0011_m6_exam_snapshots"
down_revision = "0010_m6_exam_drafts"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("exam_questions", sa.Column("frozen_content", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("exam_questions", "frozen_content")
