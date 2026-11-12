"""Student-facing attempt contract; no answer keys or grading data."""

from datetime import UTC, datetime
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.exam_attempt import AttemptStatus


class AnswerIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    selected_option_ids: list[Annotated[int, Field(strict=True, gt=0)]] | None = Field(default=None, max_length=6)
    essay_text: str | None = None

    @field_validator("essay_text")
    @classmethod
    def text_fits_database(cls, value: str | None) -> str | None:
        # MySQL TEXT is limited to 65,535 bytes, not characters.
        if value is not None:
            try:
                size = len(value.encode("utf-8"))
            except UnicodeEncodeError as exc:
                raise ValueError("Câu trả lời chứa ký tự không hợp lệ") from exc
            if size > 65535:
                raise ValueError("Câu trả lời vượt quá dung lượng cho phép")
        return value


class StudentOptionOut(BaseModel):
    id: int
    content: str


class StudentQuestionOut(BaseModel):
    question_id: int
    type: Literal["single", "multiple", "true_false", "essay"]
    content: str
    points: Decimal
    options: list[StudentOptionOut]
    selected_option_ids: list[int] | None
    essay_text: str | None


class AttemptOut(BaseModel):
    id: int
    exam_id: int
    exam_title: str
    require_fullscreen: bool
    attempt_no: int
    status: AttemptStatus
    started_at: datetime
    deadline_at: datetime
    server_now: datetime
    questions: list[StudentQuestionOut]
    class_id: int
    record_events: bool
    violation_types: list[str]
    max_violations: int
    auto_submit_on_violation: bool
    violation_count: int
    is_auto_submitted: bool

    @field_validator("started_at", "deadline_at", "server_now")
    @classmethod
    def explicit_utc(cls, value: datetime) -> datetime:
        # MySQL returns the stored UTC DATETIME without timezone information.
        return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


class StudentExamOut(BaseModel):
    id: int
    title: str
    description: str | None
    duration_min: int
    open_at: datetime
    close_at: datetime
    max_attempts: int
    used_attempts: int
    question_count: int
    record_events: bool
    violation_types: list[str]
    max_violations: int
    auto_submit_on_violation: bool
    require_fullscreen: bool
    active_attempt_id: int | None
    status: Literal["upcoming", "available", "in_progress", "retry_available", "completed", "closed"]

    @field_validator("open_at", "close_at")
    @classmethod
    def explicit_utc(cls, value: datetime) -> datetime:
        return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


class StudentExamListOut(BaseModel):
    items: list[StudentExamOut]
    total: int
    page: int
    page_size: int
