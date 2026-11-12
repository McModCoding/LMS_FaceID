from datetime import UTC, datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ExamCloseTimeIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    close_at: datetime

    @field_validator("close_at")
    @classmethod
    def explicit_time(cls, value):
        if value.tzinfo is None:
            raise ValueError("Thời gian phải có múi giờ")
        return value.astimezone(UTC)


class ExamEventIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    event_id: UUID
    type: Literal["tab_hidden", "window_blur", "fullscreen_exit", "copy", "paste", "reconnect"]


class ExamEventReceipt(BaseModel):
    recorded: bool
    violation_count: int
    status: str
    is_auto_submitted: bool


class EssayGradeIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    score: Decimal = Field(ge=0, max_digits=18, decimal_places=8)
    feedback: str | None = Field(default=None, max_length=5000)


class AttemptSummaryOut(BaseModel):
    id: int
    student_id: int
    student_code: str
    student_name: str
    attempt_no: int
    status: str
    score: Decimal | None
    score10: Decimal | None
    submitted_at: datetime | None
    violation_count: int
    is_auto_submitted: bool


class AttemptListOut(BaseModel):
    items: list[AttemptSummaryOut]
    total: int
    page: int
    page_size: int


class AttemptReviewOut(AttemptSummaryOut):
    exam_id: int
    class_id: int
    exam_title: str
    total_points: Decimal
    questions: list[dict]


class ExamResultsOut(BaseModel):
    exam_id: int
    class_id: int
    title: str
    available: bool
    reason: str
    score_policy: str
    selected_attempt_id: int | None
    score10: Decimal | None
    attempts: list[dict]


class ExamStatsOut(BaseModel):
    exam_id: int
    score_policy: str
    in_progress: int
    submitted: int
    pending_grading: int
    graded_students: int
    average: Decimal | None
    highest: Decimal | None
    lowest: Decimal | None
    histogram: list[dict]
    questions: list[dict]
    not_started: list[dict]


class ExamEventListOut(BaseModel):
    items: list[dict]
    total: int
    page: int
    page_size: int
