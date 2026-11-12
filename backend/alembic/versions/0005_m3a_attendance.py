"""
Revision ID: 0005_m3a_attendance
Revises: 0004_m2a_classes
Create Date: 2026-10-06

M3a: Thêm cột vòng đời cho sessions, bảng attendance_records,
     attendance_history, leave_requests.
"""

from __future__ import annotations

import sqlalchemy as sa

# Revision ID: 0005_m3a_attendance
# Revises: 0004_m2a_classes
from alembic import op

revision = "0005_m3a_attendance"
down_revision = "0004_m2a_classes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── 1. Thêm cột vòng đời vào sessions ───────────────────────────────────
    op.add_column("sessions", sa.Column("opened_by", sa.BigInteger(), nullable=True))
    op.add_column("sessions", sa.Column("closed_by", sa.BigInteger(), nullable=True))
    op.add_column(
        "sessions",
        sa.Column("auto_closed", sa.Boolean(), nullable=False, server_default=sa.text("0")),
    )
    op.create_foreign_key(
        "fk_sessions_opened_by_users",
        "sessions", "users",
        ["opened_by"], ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_sessions_closed_by_users",
        "sessions", "users",
        ["closed_by"], ["id"],
        ondelete="SET NULL",
    )

    # ── 2. attendance_records ────────────────────────────────────────────────
    op.create_table(
        "attendance_records",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("session_id", sa.BigInteger(), nullable=False),
        sa.Column("student_id", sa.BigInteger(), nullable=False),
        sa.Column(
            "status",
            sa.Enum("present", "late", "absent", "excused", name="attendancestatus"),
            nullable=False,
            server_default="absent",
        ),
        sa.Column(
            "source",
            sa.Enum("face", "manual", "leave", "system", name="attendancesource"),
            nullable=False,
            server_default="system",
        ),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("hit_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("modified_by", sa.BigInteger(), nullable=True),
        sa.Column("modified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
            onupdate=sa.text("NOW()"),
        ),
        sa.ForeignKeyConstraint(["session_id"], ["sessions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["student_id"], ["students.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["modified_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("session_id", "student_id", name="uq_attendance_session_student"),
    )
    op.create_index("ix_attendance_records_session_status", "attendance_records", ["session_id", "status"])
    op.create_index("ix_attendance_records_student_id", "attendance_records", ["student_id"])

    # ── 3. attendance_history ────────────────────────────────────────────────
    op.create_table(
        "attendance_history",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("record_id", sa.BigInteger(), nullable=False),
        sa.Column(
            "old_status",
            sa.Enum("present", "late", "absent", "excused", name="attendancestatus"),
            nullable=False,
        ),
        sa.Column(
            "new_status",
            sa.Enum("present", "late", "absent", "excused", name="attendancestatus"),
            nullable=False,
        ),
        sa.Column(
            "old_source",
            sa.Enum("face", "manual", "leave", "system", name="attendancesource"),
            nullable=False,
        ),
        sa.Column(
            "new_source",
            sa.Enum("face", "manual", "leave", "system", name="attendancesource"),
            nullable=False,
        ),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("changed_by", sa.BigInteger(), nullable=True),
        sa.Column("changed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.ForeignKeyConstraint(["record_id"], ["attendance_records.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["changed_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_attendance_history_record_id", "attendance_history", ["record_id"])

    # ── 4. leave_requests ────────────────────────────────────────────────────
    op.create_table(
        "leave_requests",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("student_id", sa.BigInteger(), nullable=False),
        sa.Column("session_id", sa.BigInteger(), nullable=False),
        sa.Column("reason", sa.String(500), nullable=False),
        sa.Column("attachment_path", sa.String(500), nullable=True),  # M5a
        sa.Column(
            "status",
            sa.Enum("pending", "approved", "rejected", name="leaverequeststatus"),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("reviewed_by", sa.BigInteger(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("review_note", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
            onupdate=sa.text("NOW()"),
        ),
        sa.ForeignKeyConstraint(["student_id"], ["students.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["session_id"], ["sessions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["reviewed_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_leave_requests_session_status", "leave_requests", ["session_id", "status"])
    op.create_index("ix_leave_requests_student_id", "leave_requests", ["student_id"])


def downgrade() -> None:
    op.drop_table("leave_requests")
    op.drop_table("attendance_history")
    op.drop_table("attendance_records")

    op.drop_constraint("fk_sessions_closed_by_users", "sessions", type_="foreignkey")
    op.drop_constraint("fk_sessions_opened_by_users", "sessions", type_="foreignkey")
    op.drop_column("sessions", "auto_closed")
    op.drop_column("sessions", "closed_by")
    op.drop_column("sessions", "opened_by")

    # Xóa ENUM types (MySQL tự xử lý khi drop table, không cần lệnh riêng)
