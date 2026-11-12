"""Remember processed FaceID frame IDs without storing camera images."""

import sqlalchemy as sa

from alembic import op

revision = "0014_face_frame_idempotency"
down_revision = "0013_m6_score_capacity"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "recognition_frames",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("session_id", sa.BigInteger(), nullable=False),
        sa.Column("frame_id", sa.String(36), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("response", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.ForeignKeyConstraint(["session_id"], ["sessions.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("session_id", "frame_id", name="uq_recognition_frame"),
    )
    op.create_index("ix_recognition_frames_session_id", "recognition_frames", ["session_id"])


def downgrade() -> None:
    op.drop_table("recognition_frames")
