from typing import TYPE_CHECKING

from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.lecturer import Lecturer
    from app.models.student import Student
    from app.models.subject import Subject


class Department(Base):
    __tablename__ = "departments"

    code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)

    students: Mapped[list["Student"]] = relationship(back_populates="department")
    lecturers: Mapped[list["Lecturer"]] = relationship(back_populates="department_ref")
    subjects: Mapped[list["Subject"]] = relationship(back_populates="department")
