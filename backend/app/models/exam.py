"""M6.2: exam authoring. Student attempts are a later slice."""

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
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class ExamStatus(str, enum.Enum):
    draft = "draft"
    published = "published"
    closed = "closed"


class ScorePolicy(str, enum.Enum):
    highest = "highest"
    last = "last"


class ShowResult(str, enum.Enum):
    never = "never"
    after_submit = "after_submit"
    after_close = "after_close"


class Exam(Base):
    __tablename__ = "exams"

    class_id: Mapped[int] = mapped_column(ForeignKey("classes.id", ondelete="RESTRICT"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    duration_min: Mapped[int] = mapped_column(Integer, nullable=False)
    open_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    close_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    shuffle_questions: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    shuffle_options: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    score_policy: Mapped[ScorePolicy] = mapped_column(Enum(ScorePolicy), nullable=False)
    show_result: Mapped[ShowResult] = mapped_column(Enum(ShowResult), nullable=False)
    require_fullscreen: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    record_events: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    violation_types: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    max_violations: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    auto_submit_on_violation: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    status: Mapped[ExamStatus] = mapped_column(Enum(ExamStatus), nullable=False, default=ExamStatus.draft)
    questions: Mapped[list["ExamQuestion"]] = relationship(
        back_populates="exam", cascade="all, delete-orphan", order_by="ExamQuestion.order_no"
    )


class ExamQuestion(Base):
    __tablename__ = "exam_questions"
    __table_args__ = (
        UniqueConstraint("exam_id", "question_id", name="uq_exam_question"),
        UniqueConstraint("exam_id", "order_no", name="uq_exam_question_order"),
    )
    exam_id: Mapped[int] = mapped_column(ForeignKey("exams.id", ondelete="CASCADE"), nullable=False, index=True)
    question_id: Mapped[int] = mapped_column(ForeignKey("questions.id", ondelete="RESTRICT"), nullable=False, index=True)
    points: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    order_no: Mapped[int] = mapped_column(Integer, nullable=False)
    frozen_content: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    exam: Mapped[Exam] = relationship(back_populates="questions")
    question = relationship("Question")
