"""add token_version

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-04 03:00:00.000000

"""
import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = '0003'
down_revision = '0002_m1_danh_muc_va_nguoi_dung'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('users', sa.Column('token_version', sa.Integer(), server_default='1', nullable=False))


def downgrade() -> None:
    op.drop_column('users', 'token_version')
