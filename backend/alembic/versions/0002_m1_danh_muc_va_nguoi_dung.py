"""m1_danh_muc_va_nguoi_dung

Revision ID: 0002_m1_danh_muc_va_nguoi_dung
Revises: d04d9dcce6c8
Create Date: 2026-10-04 00:00:00.000000

"""
import sqlalchemy as sa

from alembic import op

revision = '0002_m1_danh_muc_va_nguoi_dung'
down_revision = 'd04d9dcce6c8'
branch_labels = None
depends_on = None


def upgrade():
    # Update users table
    op.add_column('users', sa.Column('must_change_password', sa.Boolean(), server_default='0', nullable=False))
    op.add_column('users', sa.Column('is_deleted', sa.Boolean(), server_default='0', nullable=False))
    op.create_index(op.f('ix_users_is_deleted'), 'users', ['is_deleted'], unique=False)

    # Create lecturers table
    op.create_table(
        'lecturers',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.BigInteger(), nullable=False),
        sa.Column('code', sa.String(length=50), nullable=False),
        sa.Column('full_name', sa.String(length=255), nullable=False),
        sa.Column('phone', sa.String(length=20), nullable=True),
        sa.Column('degree', sa.String(length=100), nullable=True),
        sa.Column('department', sa.String(length=255), nullable=True),
        sa.Column('type', sa.Enum('full_time', 'visiting', name='lecturertype'), nullable=False),
        sa.Column('is_deleted', sa.Boolean(), server_default='0', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_lecturers_code'), 'lecturers', ['code'], unique=True)
    op.create_index(op.f('ix_lecturers_is_deleted'), 'lecturers', ['is_deleted'], unique=False)
    op.create_index(op.f('ix_lecturers_user_id'), 'lecturers', ['user_id'], unique=True)

    # Create students table
    op.create_table(
        'students',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.BigInteger(), nullable=False),
        sa.Column('student_code', sa.String(length=50), nullable=False),
        sa.Column('full_name', sa.String(length=255), nullable=False),
        sa.Column('admin_class', sa.String(length=100), nullable=True),
        sa.Column('dob', sa.Date(), nullable=True),
        sa.Column('gender', sa.String(length=20), nullable=True),
        sa.Column('phone', sa.String(length=20), nullable=True),
        sa.Column('email', sa.String(length=255), nullable=True),
        sa.Column('status', sa.Enum('studying', 'suspended', 'graduated', name='studentstatus'), nullable=False),
        sa.Column('is_deleted', sa.Boolean(), server_default='0', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_students_is_deleted'), 'students', ['is_deleted'], unique=False)
    op.create_index(op.f('ix_students_student_code'), 'students', ['student_code'], unique=True)
    op.create_index(op.f('ix_students_user_id'), 'students', ['user_id'], unique=True)

    # Create semesters table
    op.create_table(
        'semesters',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('start_date', sa.Date(), nullable=False),
        sa.Column('end_date', sa.Date(), nullable=False),
        sa.Column('is_current', sa.Boolean(), server_default='0', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )

    # Create subjects table
    op.create_table(
        'subjects',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('code', sa.String(length=50), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('credits', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_subjects_code'), 'subjects', ['code'], unique=True)

    # Create audit_logs table
    op.create_table(
        'audit_logs',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.BigInteger(), nullable=True),
        sa.Column('action', sa.String(length=100), nullable=False),
        sa.Column('entity', sa.String(length=100), nullable=False),
        sa.Column('entity_id', sa.String(length=100), nullable=True),
        sa.Column('detail', sa.JSON(), nullable=True),
        sa.Column('ip', sa.String(length=50), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )


def downgrade():
    op.drop_table('audit_logs')
    op.drop_index(op.f('ix_subjects_code'), table_name='subjects')
    op.drop_table('subjects')
    op.drop_table('semesters')
    op.drop_index(op.f('ix_students_user_id'), table_name='students')
    op.drop_index(op.f('ix_students_student_code'), table_name='students')
    op.drop_index(op.f('ix_students_is_deleted'), table_name='students')
    op.drop_table('students')
    op.drop_index(op.f('ix_lecturers_user_id'), table_name='lecturers')
    op.drop_index(op.f('ix_lecturers_code'), table_name='lecturers')
    op.drop_index(op.f('ix_lecturers_is_deleted'), table_name='lecturers')
    op.drop_table('lecturers')
    op.drop_index(op.f('ix_users_is_deleted'), table_name='users')
    op.drop_column('users', 'is_deleted')
    op.drop_column('users', 'must_change_password')
