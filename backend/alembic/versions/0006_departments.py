"""Add the academic department catalogue and ownership references.

Revision ID: 0006_departments
Revises: 0005_m3a_attendance
"""

import sqlalchemy as sa

from alembic import op

revision = "0006_departments"
down_revision = "0005_m3a_attendance"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "departments",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("code", sa.String(length=20), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code", name="uq_departments_code"),
        sa.UniqueConstraint("name", name="uq_departments_name"),
    )
    op.create_index("ix_departments_is_active", "departments", ["is_active"])

    # Nullable during rollout so existing production data can be assigned deliberately.
    for table_name in ("students", "lecturers", "subjects"):
        op.add_column(table_name, sa.Column("department_id", sa.BigInteger(), nullable=True))
        op.create_index(f"ix_{table_name}_department_id", table_name, ["department_id"])
        op.create_foreign_key(
            f"fk_{table_name}_department_id_departments",
            table_name,
            "departments",
            ["department_id"],
            ["id"],
            ondelete="RESTRICT",
        )


def downgrade() -> None:
    for table_name in ("subjects", "lecturers", "students"):
        op.drop_constraint(f"fk_{table_name}_department_id_departments", table_name, type_="foreignkey")
        op.drop_index(f"ix_{table_name}_department_id", table_name=table_name)
        op.drop_column(table_name, "department_id")
    op.drop_index("ix_departments_is_active", table_name="departments")
    op.drop_table("departments")
