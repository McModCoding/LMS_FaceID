import enum
from datetime import date, datetime, time
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, Boolean, Date, DateTime, Enum, ForeignKey, Integer, String, Time
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.attendance import AttendanceRecord, LeaveRequest
    from app.models.class_ import Class
    from app.models.schedule import Schedule
    from app.models.user import User


class SessionStatus(str, enum.Enum):
    scheduled = "scheduled"
    open = "open"
    closed = "closed"
    cancelled = "cancelled"


class Session(Base):
    __tablename__ = "sessions"

    class_id: Mapped[int] = mapped_column(ForeignKey("classes.id"), nullable=False, index=True)
    # Nullable vì buổi bù thủ công không có schedule_id
    schedule_id: Mapped[int | None] = mapped_column(ForeignKey("schedules.id"), nullable=True, index=True)
    session_no: Mapped[int] = mapped_column(Integer, nullable=False)
    # DATE/TIME giờ địa phương Asia/Ho_Chi_Minh
    date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    start_time: Mapped[time] = mapped_column(Time, nullable=False)
    end_time: Mapped[time] = mapped_column(Time, nullable=False)
    room: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[SessionStatus] = mapped_column(
        Enum(SessionStatus), nullable=False, default=SessionStatus.scheduled, index=True
    )
    opened_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # M3a: cột vòng đời mới
    opened_by: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    closed_by: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    auto_closed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    class_: Mapped["Class"] = relationship("Class", backref="sessions")
    schedule: Mapped["Schedule | None"] = relationship("Schedule", backref="sessions")
    opener: Mapped["User | None"] = relationship(
        "User", foreign_keys=[opened_by], backref="opened_sessions"
    )
    closer: Mapped["User | None"] = relationship(
        "User", foreign_keys=[closed_by], backref="closed_sessions"
    )
    attendance_records: Mapped[list["AttendanceRecord"]] = relationship(
        "AttendanceRecord", back_populates="session", cascade="all, delete-orphan"
    )
    leave_requests: Mapped[list["LeaveRequest"]] = relationship(
        "LeaveRequest", back_populates="session", cascade="all, delete-orphan"
    )
