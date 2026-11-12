"""
schemas/report.py
Pydantic schemas cho báo cáo chuyên cần.
"""

from __future__ import annotations

import datetime
from decimal import Decimal

from pydantic import BaseModel


class StudentAttendanceSummary(BaseModel):
    """Tổng hợp chuyên cần một sinh viên trong một lớp."""

    student_id: int
    student_code: str
    full_name: str
    admin_class: str | None = None
    is_dropped: bool = False

    # Số liệu
    total_sessions: int = 0   # tổng buổi closed không hủy
    present_count: int = 0
    late_count: int = 0
    absent_count: int = 0
    excused_count: int = 0
    attendance_rate: float | None = None  # (present+late)/total, None nếu total=0

    attendance_score: Decimal | None = None  # None nếu chưa có buổi closed
    has_warning: bool = False  # absent >= attendance_warning_absences


class AttendanceReportResponse(BaseModel):
    items: list[StudentAttendanceSummary]
    total: int
    page: int
    page_size: int


class AttendanceMatrixCell(BaseModel):
    """Một ô trong ma trận."""
    status: str | None = None  # None nếu sinh viên chưa enrolled tại buổi đó


class AttendanceMatrixRow(BaseModel):
    """Một hàng trong ma trận (một sinh viên)."""

    student_id: int
    student_code: str
    full_name: str
    is_dropped: bool = False
    cells: list[AttendanceMatrixCell]  # theo thứ tự buổi closed


class AttendanceMatrixResponse(BaseModel):
    sessions: list[dict]  # [{id, session_no, date, start_time}]
    items: list[AttendanceMatrixRow]
    total: int
    page: int
    page_size: int


class MyAttendanceSummary(BaseModel):
    """Sinh viên xem chuyên cần của mình trong một lớp."""

    class_id: int
    class_code: str | None = None
    subject_name: str | None = None
    attendance_score: Decimal | None = None
    total_sessions: int = 0
    present_count: int = 0
    late_count: int = 0
    absent_count: int = 0
    excused_count: int = 0
    has_warning: bool = False
    warning_threshold: int = 3


class MyAttendanceRecord(BaseModel):
    """Một bản ghi điểm danh của sinh viên (xem của mình)."""

    session_id: int
    session_no: int
    date: datetime.date
    start_time: datetime.time
    end_time: datetime.time
    room: str
    session_status: str
    status: str
    display_status: str
    source: str
    first_seen_at: datetime.datetime | None = None
    note: str | None = None


class MyAttendanceResponse(BaseModel):
    """GET /me/attendance"""

    summary: MyAttendanceSummary
    records: list[MyAttendanceRecord]
    total: int
