"""Prepare attempt and answer persistence.

Revision ID: 0012_m6_exam_attempts
Revises: 0011_m6_exam_snapshots
"""

import sqlalchemy as sa

from alembic import op

revision = "0012_m6_exam_attempts"
down_revision = "0011_m6_exam_snapshots"
branch_labels = None
depends_on = None


def _timestamps():
    return [sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False)]


def upgrade() -> None:
    op.create_table("exam_attempts",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("exam_id", sa.BigInteger(), sa.ForeignKey("exams.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("student_id", sa.BigInteger(), sa.ForeignKey("students.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("attempt_no", sa.Integer(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deadline_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("submitted_at", sa.DateTime(timezone=True)),
        sa.Column("is_auto_submitted", sa.Boolean(), nullable=False),
        sa.Column("status", sa.Enum("in_progress", "submitted", "auto_submitted", "graded", name="attemptstatus"), nullable=False),
        sa.Column("question_order", sa.JSON(), nullable=False), sa.Column("option_order", sa.JSON(), nullable=False),
        sa.Column("score", sa.Numeric(18, 8)), sa.Column("violation_count", sa.Integer(), nullable=False),
        *_timestamps(), sa.UniqueConstraint("exam_id", "student_id", "attempt_no", name="uq_exam_attempt_number"))
    for column in ("exam_id", "student_id", "deadline_at"):
        op.create_index(f"ix_exam_attempts_{column}", "exam_attempts", [column])
    op.create_table("attempt_answers", sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("attempt_id", sa.BigInteger(), sa.ForeignKey("exam_attempts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("question_id", sa.BigInteger(), sa.ForeignKey("questions.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("selected_option_ids", sa.JSON()), sa.Column("essay_text", sa.Text()),
        sa.Column("score", sa.Numeric(18, 8)), sa.Column("feedback", sa.Text()),
        sa.Column("saved_at", sa.DateTime(timezone=True), nullable=False), *_timestamps(),
        sa.UniqueConstraint("attempt_id", "question_id", name="uq_attempt_answer"))
    for column in ("attempt_id", "question_id"):
        op.create_index(f"ix_attempt_answers_{column}", "attempt_answers", [column])


def downgrade() -> None:
    op.drop_table("attempt_answers")
    op.drop_table("exam_attempts")
