from __future__ import annotations

from datetime import UTC, datetime

from pydantic import AwareDatetime, BaseModel, Field, field_validator

from app.models.learning import AssignmentStatus


class AssignmentIn(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str | None = None
    due_at: AwareDatetime
    max_score: float = Field(default=10, gt=0, le=1000)
    allow_late: bool = False
    status: AssignmentStatus = AssignmentStatus.draft

    @field_validator("due_at")
    @classmethod
    def normalize_deadline(cls, value: datetime) -> datetime:
        return value.astimezone(UTC)


class AssignmentOut(BaseModel):
    id: int
    class_id: int
    title: str
    description: str | None
    due_at: datetime
    max_score: float
    allow_late: bool
    status: AssignmentStatus
    created_at: datetime
    has_attachment: bool = False
    my_submission_id: int | None = None
    my_submitted_at: datetime | None = None
    my_is_late: bool | None = None
    my_has_file: bool = False
    my_score: float | None = None
    my_feedback: str | None = None
    availability: str | None = None
    can_submit: bool | None = None
    pending_count: int | None = None
    model_config = {"from_attributes": True}


class AssignmentList(BaseModel):
    items: list[AssignmentOut]
    total: int
    page: int
    page_size: int


class SubmissionTextIn(BaseModel):
    text: str | None = Field(default=None, max_length=10000)


class SubmissionOut(BaseModel):
    id: int
    assignment_id: int
    student_id: int
    student_code: str | None = None
    student_name: str | None = None
    text: str | None
    has_file: bool = False
    submitted_at: datetime
    is_late: bool
    score: float | None
    feedback: str | None
    graded_at: datetime | None
    model_config = {"from_attributes": True}


class SubmissionList(BaseModel):
    items: list[SubmissionOut]
    total: int
    page: int
    page_size: int


class SubmissionGradeIn(BaseModel):
    score: float = Field(ge=0)
    feedback: str | None = Field(default=None, max_length=5000)


class AnnouncementIn(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    content: str = Field(min_length=1, max_length=10000)
    is_pinned: bool = False


class AnnouncementOut(BaseModel):
    id: int
    class_id: int | None
    author_name: str
    title: str
    content: str
    is_pinned: bool
    created_at: datetime


class NotificationOut(BaseModel):
    id: int
    type: str
    title: str
    body: str
    link: str | None
    is_read: bool
    read_at: datetime | None
    created_at: datetime
    model_config = {"from_attributes": True}


class NotificationList(BaseModel):
    items: list[NotificationOut]
    total: int
    unread_count: int
    page: int
    page_size: int


class GroupIn(BaseModel):
    name: str = Field(min_length=1, max_length=100)


class GroupMemberIn(BaseModel):
    student_id: int


class GroupRandomizeIn(BaseModel):
    group_count: int | None = Field(default=None, ge=1, le=100)
    members_per_group: int | None = Field(default=None, ge=1, le=100)
    replace_existing: bool = False


class GroupOut(BaseModel):
    id: int
    class_id: int
    name: str
    members: list[dict]
