import enum
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Enum, Float, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.lecturer import Lecturer
    from app.models.semester import Semester
    from app.models.student import Student
    from app.models.subject import Subject


class ClassStatus(str, enum.Enum):
    draft = "draft"
    active = "active"
    closed = "closed"


class ClassStudentStatus(str, enum.Enum):
    enrolled = "enrolled"
    dropped = "dropped"


class Class(Base):
    __tablename__ = "classes"

    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    subject_id: Mapped[int] = mapped_column(ForeignKey("subjects.id"), nullable=False, index=True)
    semester_id: Mapped[int] = mapped_column(ForeignKey("semesters.id"), nullable=False, index=True)
    lecturer_id: Mapped[int | None] = mapped_column(ForeignKey("lecturers.id"), nullable=True, index=True)
    max_students: Mapped[int] = mapped_column(Integer, nullable=False, default=50)
    status: Mapped[ClassStatus] = mapped_column(
        Enum(ClassStatus), nullable=False, default=ClassStatus.draft, index=True
    )
    # Cài đặt điểm danh (lưu, dùng ở M3)
    late_after_min: Mapped[int] = mapped_column(Integer, nullable=False, default=10)
    absent_after_min: Mapped[int] = mapped_column(Integer, nullable=False, default=30)
    weight_present: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    weight_late: Mapped[float] = mapped_column(Float, nullable=False, default=0.5)
    weight_excused: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    attendance_warning_absences: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    # Xóa mềm
    is_deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)

    subject: Mapped["Subject"] = relationship("Subject", backref="classes")
    semester: Mapped["Semester"] = relationship("Semester", backref="classes")
    lecturer: Mapped["Lecturer | None"] = relationship("Lecturer", backref="classes")
    class_students: Mapped[list["ClassStudent"]] = relationship("ClassStudent", back_populates="class_", cascade="all, delete-orphan")


class ClassStudent(Base):
    __tablename__ = "class_students"
    __table_args__ = (UniqueConstraint("class_id", "student_id", name="uq_class_student"),)

    class_id: Mapped[int] = mapped_column(ForeignKey("classes.id"), nullable=False, index=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id"), nullable=False, index=True)
    status: Mapped[ClassStudentStatus] = mapped_column(
        Enum(ClassStudentStatus), nullable=False, default=ClassStudentStatus.enrolled, index=True
    )

    class_: Mapped["Class"] = relationship("Class", back_populates="class_students")
    student: Mapped["Student"] = relationship("Student", backref="class_enrollments")
