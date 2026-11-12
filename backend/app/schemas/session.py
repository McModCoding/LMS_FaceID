import datetime
from datetime import time

from pydantic import BaseModel, Field, model_validator

from app.models.session import SessionStatus


class SessionUpdate(BaseModel):
    """Sửa ngày/giờ/phòng của một buổi chưa mở (scheduled)."""

    date: datetime.date | None = None
    start_time: time | None = None
    end_time: time | None = None
    room: str | None = Field(None, min_length=1, max_length=100)

    @model_validator(mode="after")
    def validate_times(self) -> "SessionUpdate":
        st = self.start_time
        et = self.end_time
        if st is not None and et is not None and st >= et:
            raise ValueError("start_time phải trước end_time")
        return self


class SessionMakeupCreate(BaseModel):
    """Thêm buổi bù thủ công."""

    date: datetime.date
    start_time: time
    end_time: time
    room: str = Field(..., min_length=1, max_length=100)

    @model_validator(mode="after")
    def validate_times(self) -> "SessionMakeupCreate":
        if self.start_time >= self.end_time:
            raise ValueError("start_time phải trước end_time")
        return self


class SessionOut(BaseModel):
    id: int
    class_id: int
    schedule_id: int | None = None
    session_no: int
    date: datetime.date
    start_time: time
    end_time: time
    room: str
    status: SessionStatus
    opened_at: datetime.datetime | None = None
    closed_at: datetime.datetime | None = None
    # M3a
    opened_by: int | None = None
    closed_by: int | None = None
    auto_closed: bool = False
    created_at: datetime.datetime

    model_config = {"from_attributes": True}


class SessionListResponse(BaseModel):
    items: list[SessionOut]
    total: int
    page: int
    page_size: int


class SessionOpenRequest(BaseModel):
    """Yêu cầu mở buổi học. Admin mở ngoài cửa sổ phải có reason."""
    reason: str | None = Field(None, max_length=500)


class SessionReopenRequest(BaseModel):
    """Mở lại buổi đã đóng — chỉ Admin, bắt buộc reason."""
    reason: str = Field(..., min_length=1, max_length=500)

