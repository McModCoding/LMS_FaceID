"""Allow the sum of all permitted question points.

Revision ID: 0013_m6_score_capacity
Revises: 0012_m6_exam_attempts
"""

import sqlalchemy as sa

from alembic import op

revision = "0013_m6_score_capacity"
down_revision = "0012_m6_exam_attempts"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("exam_attempts", "score", existing_type=sa.Numeric(18, 8),
                    type_=sa.Numeric(24, 8), existing_nullable=True)


def downgrade() -> None:
    op.alter_column("exam_attempts", "score", existing_type=sa.Numeric(24, 8),
                    type_=sa.Numeric(18, 8), existing_nullable=True)
