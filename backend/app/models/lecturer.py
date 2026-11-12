import enum
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Enum, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.department import Department
    from app.models.user import User


class LecturerType(str, enum.Enum):
    full_time = "full_time"
    visiting = "visiting"


class Lecturer(Base):
    __tablename__ = "lecturers"

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True, nullable=False, index=True)
    department_id: Mapped[int | None] = mapped_column(ForeignKey("departments.id"), nullable=True, index=True)
    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    degree: Mapped[str | None] = mapped_column(String(100), nullable=True)
    department: Mapped[str | None] = mapped_column(String(255), nullable=True)
    type: Mapped[LecturerType] = mapped_column(Enum(LecturerType), default=LecturerType.full_time, nullable=False)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)

    user: Mapped["User"] = relationship("User", backref="lecturer_profile")
    department_ref: Mapped["Department | None"] = relationship(back_populates="lecturers")
