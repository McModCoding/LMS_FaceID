"""m2a_classes

Revision ID: 0004_m2a_classes
Revises: 0003_add_token_version
Create Date: 2026-10-04 00:00:00.000000

"""
import sqlalchemy as sa

from alembic import op

revision = "0004_m2a_classes"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade():
    # ------------------------------------------------------------------ classes
    op.create_table(
        "classes",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("code", sa.String(length=50), nullable=False),
        sa.Column("subject_id", sa.BigInteger(), nullable=False),
        sa.Column("semester_id", sa.BigInteger(), nullable=False),
        sa.Column("lecturer_id", sa.BigInteger(), nullable=True),
        sa.Column("max_students", sa.Integer(), server_default="50", nullable=False),
        sa.Column(
            "status",
            sa.Enum("draft", "active", "closed", name="classstatus"),
            server_default="draft",
            nullable=False,
        ),
        # Cài đặt điểm danh
        sa.Column("late_after_min", sa.Integer(), server_default="10", nullable=False),
        sa.Column("absent_after_min", sa.Integer(), server_default="30", nullable=False),
        sa.Column("weight_present", sa.Float(), server_default="1.0", nullable=False),
        sa.Column("weight_late", sa.Float(), server_default="0.5", nullable=False),
        sa.Column("weight_excused", sa.Float(), server_default="1.0", nullable=False),
        sa.Column("attendance_warning_absences", sa.Integer(), server_default="3", nullable=False),
        sa.Column("is_deleted", sa.Boolean(), server_default="0", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["subject_id"], ["subjects.id"]),
        sa.ForeignKeyConstraint(["semester_id"], ["semesters.id"]),
        sa.ForeignKeyConstraint(["lecturer_id"], ["lecturers.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_classes_code", "classes", ["code"], unique=True)
    op.create_index("ix_classes_subject_id", "classes", ["subject_id"], unique=False)
    op.create_index("ix_classes_semester_id", "classes", ["semester_id"], unique=False)
    op.create_index("ix_classes_lecturer_id", "classes", ["lecturer_id"], unique=False)
    op.create_index("ix_classes_status", "classes", ["status"], unique=False)
    op.create_index("ix_classes_is_deleted", "classes", ["is_deleted"], unique=False)

    # ------------------------------------------------------------ class_students
    op.create_table(
        "class_students",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("class_id", sa.BigInteger(), nullable=False),
        sa.Column("student_id", sa.BigInteger(), nullable=False),
        sa.Column(
            "status",
            sa.Enum("enrolled", "dropped", name="classstudentstatus"),
            server_default="enrolled",
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["class_id"], ["classes.id"]),
        sa.ForeignKeyConstraint(["student_id"], ["students.id"]),
        sa.UniqueConstraint("class_id", "student_id", name="uq_class_student"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_class_students_class_id", "class_students", ["class_id"], unique=False)
    op.create_index("ix_class_students_student_id", "class_students", ["student_id"], unique=False)
    # Index hiệu năng: lọc theo student_id + status
    op.create_index(
        "ix_class_students_student_status",
        "class_students",
        ["student_id", "status"],
        unique=False,
    )
    # Index hiệu năng: lọc theo class_id + status
    op.create_index(
        "ix_class_students_class_status",
        "class_students",
        ["class_id", "status"],
        unique=False,
    )

    # --------------------------------------------------------------- schedules
    op.create_table(
        "schedules",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("class_id", sa.BigInteger(), nullable=False),
        sa.Column("weekday", sa.Integer(), nullable=False),
        sa.Column("start_time", sa.Time(), nullable=False),
        sa.Column("end_time", sa.Time(), nullable=False),
        sa.Column("room", sa.String(length=100), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["class_id"], ["classes.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_schedules_class_id", "schedules", ["class_id"], unique=False)

    # ----------------------------------------------------------------- sessions
    op.create_table(
        "sessions",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("class_id", sa.BigInteger(), nullable=False),
        sa.Column("schedule_id", sa.BigInteger(), nullable=True),
        sa.Column("session_no", sa.Integer(), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("start_time", sa.Time(), nullable=False),
        sa.Column("end_time", sa.Time(), nullable=False),
        sa.Column("room", sa.String(length=100), nullable=False),
        sa.Column(
            "status",
            sa.Enum("scheduled", "open", "closed", "cancelled", name="sessionstatus"),
            server_default="scheduled",
            nullable=False,
        ),
        sa.Column("opened_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["class_id"], ["classes.id"]),
        sa.ForeignKeyConstraint(["schedule_id"], ["schedules.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    # Index hiệu năng theo yêu cầu thiết kế
    op.create_index("ix_sessions_class_id_date", "sessions", ["class_id", "date"], unique=False)
    op.create_index("ix_sessions_date", "sessions", ["date"], unique=False)
    op.create_index("ix_sessions_class_id", "sessions", ["class_id"], unique=False)
    op.create_index("ix_sessions_status", "sessions", ["status"], unique=False)


def downgrade():
    op.drop_index("ix_sessions_status", table_name="sessions")
    op.drop_index("ix_sessions_class_id", table_name="sessions")
    op.drop_index("ix_sessions_date", table_name="sessions")
    op.drop_index("ix_sessions_class_id_date", table_name="sessions")
    op.drop_table("sessions")

    op.drop_index("ix_schedules_class_id", table_name="schedules")
    op.drop_table("schedules")

    op.drop_index("ix_class_students_class_status", table_name="class_students")
    op.drop_index("ix_class_students_student_status", table_name="class_students")
    op.drop_index("ix_class_students_student_id", table_name="class_students")
    op.drop_index("ix_class_students_class_id", table_name="class_students")
    op.drop_table("class_students")

    op.drop_index("ix_classes_is_deleted", table_name="classes")
    op.drop_index("ix_classes_status", table_name="classes")
    op.drop_index("ix_classes_lecturer_id", table_name="classes")
    op.drop_index("ix_classes_semester_id", table_name="classes")
    op.drop_index("ix_classes_subject_id", table_name="classes")
    op.drop_index("ix_classes_code", table_name="classes")
    op.drop_table("classes")

    op.execute("DROP TYPE IF EXISTS sessionstatus")
    op.execute("DROP TYPE IF EXISTS classstudentstatus")
    op.execute("DROP TYPE IF EXISTS classstatus")
