"""Seed the agreed academic department catalogue.

Revision ID: 0007_seed_department_catalogue
Revises: 0006_departments
"""

from datetime import datetime

import sqlalchemy as sa

from alembic import op

revision = "0007_seed_department_catalogue"
down_revision = "0006_departments"
branch_labels = None
depends_on = None


DEPARTMENTS = (
    ("CNTT", "Khoa Công nghệ Thông tin"),
    ("CNTP", "Khoa Công nghệ Thực phẩm"),
    ("QTKD", "Khoa Quản trị Kinh doanh"),
    ("TCKT", "Khoa Tài chính - Kế toán"),
    ("TM", "Khoa Thương mại"),
    ("DLAT", "Khoa Du lịch và Ẩm thực"),
    ("NN", "Khoa Ngoại ngữ"),
    ("LUAT", "Khoa Luật"),
    ("KTQLCN", "Khoa Kinh tế và Quản lý Công nghiệp"),
    ("CK", "Khoa Công nghệ Cơ khí"),
    ("DDT", "Khoa Công nghệ Điện - Điện tử"),
    ("HH", "Khoa Công nghệ Hóa học"),
)


def upgrade() -> None:
    departments = sa.table(
        "departments",
        sa.column("code", sa.String),
        sa.column("name", sa.String),
        sa.column("is_active", sa.Boolean),
        sa.column("created_at", sa.DateTime),
        sa.column("updated_at", sa.DateTime),
    )
    now = datetime.utcnow()
    bind = op.get_bind()
    for code, name in DEPARTMENTS:
        exists = bind.execute(
            sa.text("SELECT 1 FROM departments WHERE code = :code"), {"code": code}
        ).scalar()
        if not exists:
            op.bulk_insert(
                departments,
                [{"code": code, "name": name, "is_active": True, "created_at": now, "updated_at": now}],
            )


def downgrade() -> None:
    op.execute(sa.text("DELETE FROM departments WHERE code IN :codes").bindparams(
        sa.bindparam("codes", expanding=True)
    ), {"codes": [code for code, _ in DEPARTMENTS]})
