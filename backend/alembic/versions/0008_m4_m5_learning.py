"""M4/M5: FaceID mock, assignments, announcements, notifications and groups."""
# ruff: noqa: E702

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0008_m4_m5_learning"
down_revision = "0007_seed_department_catalogue"
branch_labels = None
depends_on = None


def _timestamps(columns: list[sa.Column]) -> list[sa.Column]:
    return columns + [
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
    ]


def upgrade() -> None:
    face_status = sa.Enum("pending_embedding", "active", "revoked", name="facetemplatestatus")
    recognition_status = sa.Enum(
        "matched", "unknown", "ambiguous", "no_face", "low_quality", name="recognitionstatus"
    )
    assignment_status = sa.Enum("draft", "published", name="assignmentstatus")
    op.create_table(
        "face_consents",
        *_timestamps(
            [
                sa.Column("id", sa.BigInteger(), primary_key=True),
                sa.Column("student_id", sa.BigInteger(), nullable=False),
                sa.Column("text_version", sa.String(50), nullable=False),
                sa.Column("consented_at", sa.DateTime(timezone=True), nullable=False),
                sa.Column("revoked_at", sa.DateTime(timezone=True)),
                sa.ForeignKeyConstraint(["student_id"], ["students.id"], ondelete="CASCADE"),
            ]
        ),
    )
    op.create_index("ix_face_consents_student_id", "face_consents", ["student_id"])
    op.create_table(
        "face_templates",
        *_timestamps(
            [
                sa.Column("id", sa.BigInteger(), primary_key=True),
                sa.Column("student_id", sa.BigInteger(), nullable=False),
                sa.Column("image_path", sa.String(500), nullable=False),
                sa.Column("embedding", sa.LargeBinary()),
                sa.Column("quality_score", sa.Float()),
                sa.Column("engine_name", sa.String(100)),
                sa.Column("engine_version", sa.String(100)),
                sa.Column(
                    "status", face_status, nullable=False, server_default="pending_embedding"
                ),
                sa.ForeignKeyConstraint(["student_id"], ["students.id"], ondelete="CASCADE"),
            ]
        ),
    )
    op.create_index("ix_face_templates_student_id", "face_templates", ["student_id"])
    op.create_index("ix_face_templates_status", "face_templates", ["status"])
    op.create_table(
        "recognition_logs",
        *_timestamps(
            [
                sa.Column("id", sa.BigInteger(), primary_key=True),
                sa.Column("session_id", sa.BigInteger(), nullable=False),
                sa.Column("student_id", sa.BigInteger()),
                sa.Column("status", recognition_status, nullable=False),
                sa.Column("score", sa.Float()),
                sa.Column("margin", sa.Float()),
                sa.Column("engine_name", sa.String(100), nullable=False),
                sa.Column("frame_at", sa.DateTime(timezone=True), nullable=False),
                sa.ForeignKeyConstraint(["session_id"], ["sessions.id"], ondelete="CASCADE"),
                sa.ForeignKeyConstraint(["student_id"], ["students.id"], ondelete="SET NULL"),
            ]
        ),
    )
    op.create_index("ix_recognition_logs_session_id", "recognition_logs", ["session_id"])
    op.create_index("ix_recognition_logs_student_id", "recognition_logs", ["student_id"])
    op.create_table(
        "announcements",
        *_timestamps(
            [
                sa.Column("id", sa.BigInteger(), primary_key=True),
                sa.Column("class_id", sa.BigInteger()),
                sa.Column("author_id", sa.BigInteger(), nullable=False),
                sa.Column("title", sa.String(200), nullable=False),
                sa.Column("content", sa.Text(), nullable=False),
                sa.Column("is_pinned", sa.Boolean(), nullable=False, server_default=sa.text("0")),
                sa.ForeignKeyConstraint(["class_id"], ["classes.id"], ondelete="CASCADE"),
                sa.ForeignKeyConstraint(["author_id"], ["users.id"], ondelete="RESTRICT"),
            ]
        ),
    )
    op.create_index("ix_announcements_class_id", "announcements", ["class_id"])
    op.create_index("ix_announcements_author_id", "announcements", ["author_id"])
    op.create_table(
        "notifications",
        *_timestamps(
            [
                sa.Column("id", sa.BigInteger(), primary_key=True),
                sa.Column("user_id", sa.BigInteger(), nullable=False),
                sa.Column("type", sa.String(80), nullable=False),
                sa.Column("title", sa.String(200), nullable=False),
                sa.Column("body", sa.String(500), nullable=False),
                sa.Column("link", sa.String(300)),
                sa.Column("is_read", sa.Boolean(), nullable=False, server_default=sa.text("0")),
                sa.Column("read_at", sa.DateTime(timezone=True)),
                sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            ]
        ),
    )
    op.create_index("ix_notifications_user_id", "notifications", ["user_id"])
    op.create_index("ix_notifications_is_read", "notifications", ["is_read"])
    op.create_table(
        "assignments",
        *_timestamps(
            [
                sa.Column("id", sa.BigInteger(), primary_key=True),
                sa.Column("class_id", sa.BigInteger(), nullable=False),
                sa.Column("title", sa.String(200), nullable=False),
                sa.Column("description", sa.Text()),
                sa.Column("due_at", sa.DateTime(timezone=True), nullable=False),
                sa.Column("max_score", sa.Float(), nullable=False, server_default="10"),
                sa.Column("allow_late", sa.Boolean(), nullable=False, server_default=sa.text("0")),
                sa.Column("attachment_path", sa.String(500)),
                sa.Column("status", assignment_status, nullable=False, server_default="draft"),
                sa.ForeignKeyConstraint(["class_id"], ["classes.id"], ondelete="CASCADE"),
            ]
        ),
    )
    op.create_index("ix_assignments_class_id", "assignments", ["class_id"])
    op.create_index("ix_assignments_due_at", "assignments", ["due_at"])
    op.create_index("ix_assignments_status", "assignments", ["status"])
    op.create_table(
        "submissions",
        *_timestamps(
            [
                sa.Column("id", sa.BigInteger(), primary_key=True),
                sa.Column("assignment_id", sa.BigInteger(), nullable=False),
                sa.Column("student_id", sa.BigInteger(), nullable=False),
                sa.Column("file_path", sa.String(500)),
                sa.Column("text", sa.Text()),
                sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=False),
                sa.Column("is_late", sa.Boolean(), nullable=False, server_default=sa.text("0")),
                sa.Column("score", sa.Float()),
                sa.Column("feedback", sa.Text()),
                sa.Column("graded_by", sa.BigInteger()),
                sa.Column("graded_at", sa.DateTime(timezone=True)),
                sa.ForeignKeyConstraint(["assignment_id"], ["assignments.id"], ondelete="CASCADE"),
                sa.ForeignKeyConstraint(["student_id"], ["students.id"], ondelete="CASCADE"),
                sa.ForeignKeyConstraint(["graded_by"], ["users.id"], ondelete="SET NULL"),
                sa.UniqueConstraint(
                    "assignment_id", "student_id", name="uq_submission_assignment_student"
                ),
            ]
        ),
    )
    op.create_index("ix_submissions_assignment_id", "submissions", ["assignment_id"])
    op.create_index("ix_submissions_student_id", "submissions", ["student_id"])
    op.create_table(
        "groups",
        *_timestamps(
            [
                sa.Column("id", sa.BigInteger(), primary_key=True),
                sa.Column("class_id", sa.BigInteger(), nullable=False),
                sa.Column("name", sa.String(100), nullable=False),
                sa.ForeignKeyConstraint(["class_id"], ["classes.id"], ondelete="CASCADE"),
                sa.UniqueConstraint("class_id", "name", name="uq_group_class_name"),
            ]
        ),
    )
    op.create_index("ix_groups_class_id", "groups", ["class_id"])
    op.create_table(
        "group_members",
        *_timestamps(
            [
                sa.Column("id", sa.BigInteger(), primary_key=True),
                sa.Column("group_id", sa.BigInteger(), nullable=False),
                sa.Column("student_id", sa.BigInteger(), nullable=False),
                sa.ForeignKeyConstraint(["group_id"], ["groups.id"], ondelete="CASCADE"),
                sa.ForeignKeyConstraint(["student_id"], ["students.id"], ondelete="CASCADE"),
                sa.UniqueConstraint("group_id", "student_id", name="uq_group_member"),
            ]
        ),
    )
    op.create_index("ix_group_members_group_id", "group_members", ["group_id"])
    op.create_index("ix_group_members_student_id", "group_members", ["student_id"])


def downgrade() -> None:
    for table in (
        "group_members",
        "groups",
        "submissions",
        "assignments",
        "notifications",
        "announcements",
        "recognition_logs",
        "face_templates",
        "face_consents",
    ):
        op.drop_table(table)
