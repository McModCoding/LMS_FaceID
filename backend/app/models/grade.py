"""M7 grade configuration and manual marks."""
from datetime import datetime
from decimal import Decimal
from typing import Literal

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

GradeType = Literal["attendance", "assignment", "exam", "manual"]


class GradeComponent(Base):
    __tablename__ = "grade_components"
    __table_args__ = (
        CheckConstraint("weight >= 0 AND weight <= 100", name="ck_component_weight"),
        CheckConstraint("type IN ('attendance','assignment','exam','manual')", name="ck_component_type"),
    )
    class_id: Mapped[int] = mapped_column(ForeignKey("classes.id"), index=True)
    name: Mapped[str] = mapped_column(String(200))
    weight: Mapped[Decimal] = mapped_column(Numeric(7, 4))
    type: Mapped[str] = mapped_column(String(16))
    ref_id: Mapped[int | None] = mapped_column(nullable=True)


class Grade(Base):
    __tablename__ = "grades"
    __table_args__ = (
        UniqueConstraint("component_id", "student_id", name="uq_grade_component_student"),
        CheckConstraint("score >= 0 AND score <= 10", name="ck_grade_score"),
    )
    component_id: Mapped[int] = mapped_column(ForeignKey("grade_components.id", ondelete="CASCADE"), index=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id"), index=True)
    score: Mapped[Decimal | None] = mapped_column(Numeric(7, 4), nullable=True)
    updated_by: Mapped[int] = mapped_column(ForeignKey("users.id"))


class GradePublication(Base):
    __tablename__ = "grade_publications"
    __table_args__ = (UniqueConstraint("class_id", name="uq_grade_publication_class"),)
    class_id: Mapped[int] = mapped_column(ForeignKey("classes.id"), index=True)
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    published_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
