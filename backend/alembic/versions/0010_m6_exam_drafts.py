"""M6.2: exam drafts.

Revision ID: 0010_m6_exam_drafts
Revises: 0009_m6_question_bank
"""

import sqlalchemy as sa

from alembic import op

revision = "0010_m6_exam_drafts"
down_revision = "0009_m6_question_bank"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "exams",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("class_id", sa.BigInteger(), sa.ForeignKey("classes.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("duration_min", sa.Integer(), nullable=False),
        sa.Column("open_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("close_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("shuffle_questions", sa.Boolean(), nullable=False),
        sa.Column("shuffle_options", sa.Boolean(), nullable=False),
        sa.Column("max_attempts", sa.Integer(), nullable=False),
        sa.Column("score_policy", sa.Enum("highest", "last", name="scorepolicy"), nullable=False),
        sa.Column("show_result", sa.Enum("never", "after_submit", "after_close", name="showresult"), nullable=False),
        sa.Column("require_fullscreen", sa.Boolean(), nullable=False),
        sa.Column("record_events", sa.Boolean(), nullable=False),
        sa.Column("violation_types", sa.JSON(), nullable=False),
        sa.Column("max_violations", sa.Integer(), nullable=False),
        sa.Column("auto_submit_on_violation", sa.Boolean(), nullable=False),
        sa.Column("status", sa.Enum("draft", "published", "closed", name="examstatus"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
    )
    op.create_index("ix_exams_class_id", "exams", ["class_id"])
    op.create_table(
        "exam_questions",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("exam_id", sa.BigInteger(), sa.ForeignKey("exams.id", ondelete="CASCADE"), nullable=False),
        sa.Column("question_id", sa.BigInteger(), sa.ForeignKey("questions.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("points", sa.Numeric(12, 4), nullable=False),
        sa.Column("order_no", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.UniqueConstraint("exam_id", "question_id", name="uq_exam_question"),
        sa.UniqueConstraint("exam_id", "order_no", name="uq_exam_question_order"),
    )
    op.create_index("ix_exam_questions_exam_id", "exam_questions", ["exam_id"])
    op.create_index("ix_exam_questions_question_id", "exam_questions", ["question_id"])


def downgrade() -> None:
    op.drop_table("exam_questions")
    op.drop_table("exams")
