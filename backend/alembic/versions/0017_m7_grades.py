"""M7 grade components, manual marks and publication."""
import sqlalchemy as sa

from alembic import op

revision = "0017_m7_grades"
down_revision = "0016_m6_exam_events"
branch_labels = None
depends_on = None


def columns():
    return [sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)]


def upgrade():
    op.create_table("grade_components", *columns(),
        sa.Column("class_id", sa.BigInteger(), sa.ForeignKey("classes.id"), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("weight", sa.Numeric(7, 4), nullable=False),
        sa.Column("type", sa.String(16), nullable=False),
        sa.Column("ref_id", sa.Integer(), nullable=True),
        sa.CheckConstraint("weight >= 0 AND weight <= 100", name="ck_component_weight"),
        sa.CheckConstraint("type IN ('attendance','assignment','exam','manual')", name="ck_component_type"))
    op.create_table("grades", *columns(),
        sa.Column("component_id", sa.BigInteger(), sa.ForeignKey("grade_components.id", ondelete="CASCADE"), nullable=False),
        sa.Column("student_id", sa.BigInteger(), sa.ForeignKey("students.id"), nullable=False),
        sa.Column("score", sa.Numeric(7, 4), nullable=True),
        sa.Column("updated_by", sa.BigInteger(), sa.ForeignKey("users.id"), nullable=False),
        sa.UniqueConstraint("component_id", "student_id", name="uq_grade_component_student"),
        sa.CheckConstraint("score >= 0 AND score <= 10", name="ck_grade_score"))
    op.create_table("grade_publications", *columns(),
        sa.Column("class_id", sa.BigInteger(), sa.ForeignKey("classes.id"), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("published_by", sa.BigInteger(), sa.ForeignKey("users.id"), nullable=False),
        sa.UniqueConstraint("class_id", name="uq_grade_publication_class"))
    for table, names in [("grade_components", ["class_id"]), ("grades", ["component_id", "student_id"]), ("grade_publications", ["class_id"])]:
        for name in names:
            op.create_index(f"ix_{table}_{name}", table, [name])


def downgrade():
    op.drop_table("grade_publications")
    op.drop_table("grades")
    op.drop_table("grade_components")
