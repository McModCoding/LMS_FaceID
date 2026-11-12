from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, field_validator


class SemesterCreate(BaseModel):
    name: str
    start_date: date
    end_date: date
    is_current: bool = False

    @field_validator("end_date")
    @classmethod
    def check_dates(cls, v: date, values) -> date:
        start_date = values.data.get("start_date")
        if start_date and v < start_date:
            raise ValueError("Ngày kết thúc phải sau hoặc bằng ngày bắt đầu.")
        return v

class SemesterUpdate(BaseModel):
    name: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    is_current: bool | None = None

class SemesterRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    start_date: date
    end_date: date
    is_current: bool
    created_at: datetime
    updated_at: datetime
