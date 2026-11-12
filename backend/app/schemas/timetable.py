from datetime import date, time

from pydantic import BaseModel


class TimetableSessionOut(BaseModel):
    """Một buổi học trong thời khóa biểu."""

    session_id: int
    class_id: int
    class_code: str
    subject_name: str
    subject_code: str
    date: date
    start_time: time
    end_time: time
    room: str
    status: str
    lecturer_id: int | None = None
    lecturer_name: str | None = None

    model_config = {"from_attributes": True}


class TimetableResponse(BaseModel):
    items: list[TimetableSessionOut]
    total: int
