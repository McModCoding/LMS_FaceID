"""
models/attendance.py
Model điểm danh: AttendanceRecord, AttendanceHistory, LeaveRequest.
"""

from __future__ import annotations

import enum
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.session import Session
    from app.models.student import Student
    from app.models.user import User


class AttendanceStatus(str, enum.Enum):
    present = "present"
    late = "late"
    absent = "absent"
    excused = "excused"


class AttendanceSource(str, enum.Enum):
    face = "face"
    manual = "manual"
    leave = "leave"
    system = "system"


class LeaveRequestStatus(str, enum.Enum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"


class AttendanceRecord(Base):
    __tablename__ = "attendance_records"
    __table_args__ = (
        UniqueConstraint("session_id", "student_id", name="uq_attendance_session_student"),
    )

    session_id: Mapped[int] = mapped_column(
        ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    student_id: Mapped[int] = mapped_column(
        ForeignKey("students.id", ondelete="CASCADE"), nullable=False, index=True
    )
    status: Mapped[AttendanceStatus] = mapped_column(
        Enum(AttendanceStatus), nullable=False, default=AttendanceStatus.absent
    )
    source: Mapped[AttendanceSource] = mapped_column(
        Enum(AttendanceSource), nullable=False, default=AttendanceSource.system
    )
    first_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    hit_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    modified_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    modified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    session: Mapped[Session] = relationship("Session", back_populates="attendance_records")
    student: Mapped[Student] = relationship("Student", backref="attendance_records")
    modifier: Mapped[User | None] = relationship(
        "User", foreign_keys=[modified_by], backref="modified_attendances"
    )
    history: Mapped[list[AttendanceHistory]] = relationship(
        "AttendanceHistory", back_populates="record", cascade="all, delete-orphan"
    )


class AttendanceHistory(Base):
    __tablename__ = "attendance_history"

    record_id: Mapped[int] = mapped_column(
        ForeignKey("attendance_records.id", ondelete="CASCADE"), nullable=False, index=True
    )
    old_status: Mapped[AttendanceStatus] = mapped_column(Enum(AttendanceStatus), nullable=False)
    new_status: Mapped[AttendanceStatus] = mapped_column(Enum(AttendanceStatus), nullable=False)
    old_source: Mapped[AttendanceSource] = mapped_column(Enum(AttendanceSource), nullable=False)
    new_source: Mapped[AttendanceSource] = mapped_column(Enum(AttendanceSource), nullable=False)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    changed_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    record: Mapped[AttendanceRecord] = relationship("AttendanceRecord", back_populates="history")
    changer: Mapped[User | None] = relationship(
        "User", foreign_keys=[changed_by], backref="attendance_changes"
    )


class LeaveRequest(Base):
    __tablename__ = "leave_requests"

    student_id: Mapped[int] = mapped_column(
        ForeignKey("students.id", ondelete="CASCADE"), nullable=False, index=True
    )
    session_id: Mapped[int] = mapped_column(
        ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    reason: Mapped[str] = mapped_column(String(500), nullable=False)
    attachment_path: Mapped[str | None] = mapped_column(String(500), nullable=True)  # M5a
    status: Mapped[LeaveRequestStatus] = mapped_column(
        Enum(LeaveRequestStatus), nullable=False, default=LeaveRequestStatus.pending
    )
    reviewed_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    review_note: Mapped[str | None] = mapped_column(Text, nullable=True)

    student: Mapped[Student] = relationship("Student", backref="leave_requests")
    session: Mapped[Session] = relationship("Session", back_populates="leave_requests")
    reviewer: Mapped[User | None] = relationship(
        "User", foreign_keys=[reviewed_by], backref="reviewed_leave_requests"
    )
