from datetime import date, datetime, time

from pydantic import BaseModel, Field, model_validator


class ScheduleCreate(BaseModel):
    weekday: int = Field(..., ge=0, le=6, description="0=Thứ Hai, 6=Chủ Nhật")
    start_time: time
    end_time: time
    room: str = Field(..., min_length=1, max_length=100)
    start_date: date
    end_date: date

    @model_validator(mode="after")
    def validate_times_and_dates(self) -> "ScheduleCreate":
        if self.start_time >= self.end_time:
            raise ValueError("start_time phải trước end_time")
        if self.start_date > self.end_date:
            raise ValueError("start_date phải nhỏ hơn hoặc bằng end_date")
        return self


class ScheduleUpdate(BaseModel):
    weekday: int | None = Field(None, ge=0, le=6)
    start_time: time | None = None
    end_time: time | None = None
    room: str | None = Field(None, min_length=1, max_length=100)
    start_date: date | None = None
    end_date: date | None = None

    @model_validator(mode="after")
    def validate_times(self) -> "ScheduleUpdate":
        st = self.start_time
        et = self.end_time
        if st is not None and et is not None and st >= et:
            raise ValueError("start_time phải trước end_time")
        sd = self.start_date
        ed = self.end_date
        if sd is not None and ed is not None and sd > ed:
            raise ValueError("start_date phải nhỏ hơn hoặc bằng end_date")
        return self


class ScheduleOut(BaseModel):
    id: int
    class_id: int
    weekday: int
    start_time: time
    end_time: time
    room: str
    start_date: date
    end_date: date
    created_at: datetime

    model_config = {"from_attributes": True}
