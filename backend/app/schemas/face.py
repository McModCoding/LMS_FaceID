from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class FaceConsentIn(BaseModel):
    text_version: str = Field(min_length=1, max_length=50)


class FaceStatusOut(BaseModel):
    engine: str
    version: str
    is_ready: bool


class FaceProfileOut(BaseModel):
    consented: bool
    cleanup_pending: bool = False
    text_version: str | None = None
    consented_at: datetime | None = None
    image_count: int = 0
    status: str | None = None


class FaceEnrollmentResult(BaseModel):
    accepted: int
    rejected: int
    status: str
    items: list[dict]


class RecognitionFeedItem(BaseModel):
    id: int
    student_id: int | None
    status: str
    score: float | None
    margin: float | None
    engine_name: str
    frame_at: datetime
    model_config = {"from_attributes": True}


class RecognitionFeedOut(BaseModel):
    needs_confirmation: list[RecognitionFeedItem]
    logs: list[RecognitionFeedItem]


class RecognitionResponse(BaseModel):
    engine: str
    ready: bool
    faces: list[dict]
    attendance_changes: list[dict]


class ReindexResult(BaseModel):
    processed: int
    activated: int
