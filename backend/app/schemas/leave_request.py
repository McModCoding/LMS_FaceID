"""
schemas/leave_request.py
Pydantic schemas cho đơn xin vắng.
"""

from __future__ import annotations

import datetime

from pydantic import BaseModel, Field, field_validator

from app.models.attendance import LeaveRequestStatus


class LeaveRequestCreate(BaseModel):
    """Sinh viên gửi đơn xin vắng cho một buổi."""

    session_id: int
    reason: str = Field(..., min_length=1, max_length=500)

    @field_validator("reason", mode="before")
    @classmethod
    def strip_reason(cls, value):
        return value.strip() if isinstance(value, str) else value


class LeaveRequestOut(BaseModel):
    """Thông tin một đơn xin vắng."""

    id: int
    student_id: int
    session_id: int
    # Không trả reason trong file Excel xuất ra, nhưng API trả (chỉ người có quyền thấy)
    reason: str
    status: LeaveRequestStatus
    reviewed_by: int | None = None
    reviewed_at: datetime.datetime | None = None
    review_note: str | None = None
    created_at: datetime.datetime
    updated_at: datetime.datetime
    # Thông tin join (tùy ngữ cảnh)
    student_name: str | None = None
    student_code: str | None = None
    session_date: datetime.date | None = None
    class_id: int | None = None
    session_no: int | None = None
    reviewer_name: str | None = None

    model_config = {"from_attributes": True}


class LeaveRequestReview(BaseModel):
    """Giảng viên / Admin duyệt hoặc từ chối đơn."""

    decision: str = Field(..., pattern="^(approve|reject)$")
    review_note: str | None = Field(None, max_length=500)


class LeaveRequestListResponse(BaseModel):
    items: list[LeaveRequestOut]
    total: int
    page: int
    page_size: int
