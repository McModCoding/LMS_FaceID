"""Basic file/link materials per class."""

import sqlalchemy as sa

from alembic import op

revision = "0015_m5a_materials"
down_revision = "0014_face_frame_idempotency"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "materials",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("class_id", sa.BigInteger(), sa.ForeignKey("classes.id"), nullable=False),
        sa.Column("author_id", sa.BigInteger(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("url", sa.String(2048), nullable=True),
        sa.Column("file_path", sa.String(500), nullable=True),
        sa.Column("filename", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.CheckConstraint("(url IS NULL) <> (file_path IS NULL)", name="ck_material_one_source"),
    )
    op.create_index("ix_materials_class_id", "materials", ["class_id"])


def downgrade():
    op.drop_table("materials")
