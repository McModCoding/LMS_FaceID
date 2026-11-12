"""Persistence for exam attempts; not yet exposed as a student API."""

import enum
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    Numeric,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AttemptStatus(str, enum.Enum):
    in_progress = "in_progress"
    submitted = "submitted"
    auto_submitted = "auto_submitted"
    graded = "graded"


class ExamAttempt(Base):
    __tablename__ = "exam_attempts"
    __table_args__ = (UniqueConstraint("exam_id", "student_id", "attempt_no", name="uq_exam_attempt_number"),)
    exam_id: Mapped[int] = mapped_column(ForeignKey("exams.id", ondelete="RESTRICT"), nullable=False, index=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id", ondelete="RESTRICT"), nullable=False, index=True)
    attempt_no: Mapped[int] = mapped_column(Integer, nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    deadline_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    is_auto_submitted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    status: Mapped[AttemptStatus] = mapped_column(Enum(AttemptStatus), nullable=False, default=AttemptStatus.in_progress)
    question_order: Mapped[list[int]] = mapped_column(JSON, nullable=False)
    option_order: Mapped[dict] = mapped_column(JSON, nullable=False)
    score: Mapped[Decimal | None] = mapped_column(Numeric(24, 8))
    violation_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class AttemptAnswer(Base):
    __tablename__ = "attempt_answers"
    __table_args__ = (UniqueConstraint("attempt_id", "question_id", name="uq_attempt_answer"),)
    attempt_id: Mapped[int] = mapped_column(ForeignKey("exam_attempts.id", ondelete="CASCADE"), nullable=False, index=True)
    question_id: Mapped[int] = mapped_column(ForeignKey("questions.id", ondelete="RESTRICT"), nullable=False, index=True)
    selected_option_ids: Mapped[list[int] | None] = mapped_column(JSON, nullable=True)
    essay_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    score: Mapped[Decimal | None] = mapped_column(Numeric(18, 8), nullable=True)
    feedback: Mapped[str | None] = mapped_column(Text, nullable=True)
    saved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
