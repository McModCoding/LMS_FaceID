"""
schemas/attendance.py
Pydantic schemas cho điểm danh (attendance_records, attendance_history).
"""

from __future__ import annotations

import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.models.attendance import AttendanceSource, AttendanceStatus


class AttendanceRecordOut(BaseModel):
    """Thông tin một bản ghi điểm danh."""

    id: int
    session_id: int
    student_id: int
    # Thông tin sinh viên (join)
    student_code: str | None = None
    full_name: str | None = None
    admin_class: str | None = None
    status: AttendanceStatus
    source: AttendanceSource
    display_status: str  # "pending" khi absent+system+open; còn lại = status.value
    first_seen_at: datetime.datetime | None = None
    hit_count: int = 0
    confidence: float | None = None
    note: str | None = None
    modified_by: int | None = None
    modified_at: datetime.datetime | None = None
    is_dropped: bool = False  # sinh viên đã rút khỏi lớp

    model_config = {"from_attributes": True}


class AttendanceSummary(BaseModel):
    """Tóm tắt đếm số lượng theo từng trạng thái cho một buổi."""

    total: int = 0
    present: int = 0
    late: int = 0
    absent: int = 0
    excused: int = 0
    pending: int = 0  # absent+system trong buổi open


class SessionAttendanceResponse(BaseModel):
    """GET /sessions/{id}/attendance — danh sách + tóm tắt + meta buổi."""

    session_id: int
    session_status: str
    can_edit: bool  # người đang xem có quyền sửa không
    summary: AttendanceSummary
    items: list[AttendanceRecordOut]
    total: int
    page: int
    page_size: int


class AttendancePatch(BaseModel):
    """PATCH một bản ghi điểm danh."""

    status: AttendanceStatus
    note: str | None = Field(None, max_length=1000)
    expected_status: AttendanceStatus | None = None  # optimistic locking


class BulkAttendancePatch(BaseModel):
    """POST /sessions/{id}/attendance/bulk — sửa hàng loạt."""

    student_ids: list[int] = Field(..., min_length=1)
    status: AttendanceStatus
    note: str | None = Field(None, max_length=1000)


class MarkRemainingPatch(BaseModel):
    """POST /sessions/{id}/attendance/mark-remaining — áp status cho các pending."""

    status: AttendanceStatus
    note: str | None = Field(None, max_length=1000)


class BulkAttendanceResult(BaseModel):
    """Kết quả thao tác hàng loạt."""

    updated: int
    skipped: int = 0


class CheckInResult(BaseModel):
    """Kết quả apply_presence (check-in nhanh)."""

    student_id: int
    result_code: Literal[
        "present", "late", "OUTSIDE_WINDOW", "already_excused", "no_downgrade"
    ]
    new_status: AttendanceStatus | None = None
    message: str


class AttendanceHistoryOut(BaseModel):
    """Một dòng lịch sử thay đổi điểm danh."""

    id: int
    record_id: int
    old_status: AttendanceStatus
    new_status: AttendanceStatus
    old_source: AttendanceSource
    new_source: AttendanceSource
    note: str | None = None
    changed_by: int | None = None
    changed_by_name: str | None = None  # join
    changed_at: datetime.datetime

    model_config = {"from_attributes": True}
