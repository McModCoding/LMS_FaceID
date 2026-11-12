"""Question bank for M6, independent of exam attempts."""

import enum
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Enum, ForeignKey, Integer, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.subject import Subject
    from app.models.user import User


class QuestionType(str, enum.Enum):
    single = "single"
    multiple = "multiple"
    true_false = "true_false"
    essay = "essay"


class QuestionDifficulty(str, enum.Enum):
    easy = "easy"
    medium = "medium"
    hard = "hard"


class Question(Base):
    __tablename__ = "questions"

    subject_id: Mapped[int] = mapped_column(ForeignKey("subjects.id", ondelete="RESTRICT"), nullable=False, index=True)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True)
    type: Mapped[QuestionType] = mapped_column(Enum(QuestionType), nullable=False, index=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    difficulty: Mapped[QuestionDifficulty] = mapped_column(Enum(QuestionDifficulty), nullable=False, index=True)
    explanation: Mapped[str | None] = mapped_column(Text, nullable=True)

    subject: Mapped["Subject"] = relationship("Subject")
    author: Mapped["User"] = relationship("User")
    options: Mapped[list["QuestionOption"]] = relationship(
        "QuestionOption", back_populates="question", cascade="all, delete-orphan", order_by="QuestionOption.order_no"
    )


class QuestionOption(Base):
    __tablename__ = "question_options"
    __table_args__ = (UniqueConstraint("question_id", "order_no", name="uq_question_option_order"),)

    question_id: Mapped[int] = mapped_column(ForeignKey("questions.id", ondelete="CASCADE"), nullable=False, index=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    is_correct: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    order_no: Mapped[int] = mapped_column(Integer, nullable=False)

    question: Mapped["Question"] = relationship("Question", back_populates="options")
