"""M6.1: subject question bank.

Revision ID: 0009_m6_question_bank
Revises: 0008_m4_m5_learning
"""

import sqlalchemy as sa

from alembic import op

revision = "0009_m6_question_bank"
down_revision = "0008_m4_m5_learning"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "questions",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("subject_id", sa.BigInteger(), sa.ForeignKey("subjects.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("created_by", sa.BigInteger(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("type", sa.Enum("single", "multiple", "true_false", "essay", name="questiontype"), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("difficulty", sa.Enum("easy", "medium", "hard", name="questiondifficulty"), nullable=False),
        sa.Column("explanation", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
    )
    for column in ("subject_id", "created_by", "type", "difficulty"):
        op.create_index(f"ix_questions_{column}", "questions", [column])
    op.create_table(
        "question_options",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("question_id", sa.BigInteger(), sa.ForeignKey("questions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("is_correct", sa.Boolean(), nullable=False),
        sa.Column("order_no", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.UniqueConstraint("question_id", "order_no", name="uq_question_option_order"),
    )
    op.create_index("ix_question_options_question_id", "question_options", ["question_id"])


def downgrade() -> None:
    op.drop_table("question_options")
    op.drop_table("questions")
