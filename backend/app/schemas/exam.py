from datetime import UTC, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from app.models.exam import ExamStatus, ScorePolicy, ShowResult

EventType = Literal["tab_hidden", "window_blur", "fullscreen_exit", "copy", "paste"]


class ExamQuestionIn(BaseModel):
    question_id: int = Field(gt=0)
    points: Decimal = Field(gt=0, max_digits=12, decimal_places=4)


class ExamDraftIn(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=10000)
    duration_min: int = Field(gt=0, le=2147483647)
    open_at: datetime
    close_at: datetime
    shuffle_questions: bool = False
    shuffle_options: bool = False
    max_attempts: int = Field(ge=1, le=2147483647)
    score_policy: ScorePolicy
    show_result: ShowResult = ShowResult.after_close
    require_fullscreen: bool = False
    record_events: bool = False
    violation_types: list[EventType] = Field(default_factory=list, max_length=5)
    max_violations: int = Field(default=0, ge=0, le=2147483647)
    auto_submit_on_violation: bool = False
    questions: list[ExamQuestionIn] = Field(default_factory=list, max_length=500)

    @field_validator("title")
    @classmethod
    def clean_title(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Tên bài kiểm tra không được để trống")
        return value

    @field_validator("open_at", "close_at")
    @classmethod
    def utc_time(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("Thời gian phải có múi giờ")
        return value.astimezone(UTC)

    @model_validator(mode="after")
    def validate_draft(self):
        if self.close_at <= self.open_at:
            raise ValueError("Thời điểm đóng phải sau thời điểm mở")
        ids = [row.question_id for row in self.questions]
        if len(ids) != len(set(ids)):
            raise ValueError("Một câu hỏi chỉ được thêm một lần")
        if len(self.violation_types) != len(set(self.violation_types)):
            raise ValueError("Không chọn trùng sự kiện")
        if not self.record_events and (self.violation_types or self.auto_submit_on_violation or self.max_violations):
            raise ValueError("Cần bật ghi sự kiện để cấu hình các hành vi")
        if "fullscreen_exit" in self.violation_types and not self.require_fullscreen:
            raise ValueError("Chỉ ghi nhận thoát toàn màn hình khi bài yêu cầu toàn màn hình")
        if self.auto_submit_on_violation and (not self.violation_types or self.max_violations == 0):
            raise ValueError("Tự nộp cần ít nhất một sự kiện và ngưỡng lớn hơn 0")
        return self


class ExamQuestionOut(BaseModel):
    question_id: int
    points: Decimal
    order_no: int
    content: str
    type: str


class ExamOut(BaseModel):
    id: int
    class_id: int
    title: str
    description: str | None
    duration_min: int
    open_at: datetime
    close_at: datetime
    shuffle_questions: bool
    shuffle_options: bool
    max_attempts: int
    score_policy: ScorePolicy
    show_result: ShowResult
    require_fullscreen: bool
    record_events: bool
    violation_types: list[EventType]
    max_violations: int
    auto_submit_on_violation: bool
    status: ExamStatus
    questions: list[ExamQuestionOut]
    created_at: datetime
    has_attempts: bool = False
    total_points: Decimal = Decimal(0)


class ExamList(BaseModel):
    items: list[ExamOut]
    total: int
    page: int
    page_size: int
