import enum
from datetime import date
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Date, Enum, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.department import Department
    from app.models.user import User


class StudentStatus(str, enum.Enum):
    studying = "studying"
    suspended = "suspended"
    graduated = "graduated"


class Student(Base):
    __tablename__ = "students"

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True, nullable=False, index=True)
    department_id: Mapped[int | None] = mapped_column(ForeignKey("departments.id"), nullable=True, index=True)
    student_code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    admin_class: Mapped[str | None] = mapped_column(String(100), nullable=True)
    dob: Mapped[date | None] = mapped_column(Date, nullable=True)
    gender: Mapped[str | None] = mapped_column(String(20), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[StudentStatus] = mapped_column(Enum(StudentStatus), default=StudentStatus.studying, nullable=False)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)

    user: Mapped["User"] = relationship("User", backref="student_profile")
    department: Mapped["Department | None"] = relationship(back_populates="students")
