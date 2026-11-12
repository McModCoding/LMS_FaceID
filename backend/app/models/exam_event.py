"""Idempotent, server-timestamped behavioral indicators for exams."""

from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ExamEvent(Base):
    __tablename__ = "exam_events"
    __table_args__ = (UniqueConstraint("attempt_id", "event_id", name="uq_exam_event_request"),)

    attempt_id: Mapped[int] = mapped_column(ForeignKey("exam_attempts.id", ondelete="CASCADE"), index=True)
    event_id: Mapped[str] = mapped_column(String(36), nullable=False)
    type: Mapped[str] = mapped_column(String(32), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    counted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    meta: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
