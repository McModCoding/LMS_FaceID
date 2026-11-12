from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class SubjectCreate(BaseModel):
    code: str = Field(..., min_length=1, max_length=50)
    name: str = Field(..., min_length=1, max_length=255)
    credits: int = Field(..., ge=1, le=20)
    department_id: int | None = None

class SubjectUpdate(BaseModel):
    code: str | None = Field(None, min_length=1, max_length=50)
    name: str | None = Field(None, min_length=1, max_length=255)
    credits: int | None = Field(None, ge=1, le=20)
    department_id: int | None = None

class SubjectRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str
    name: str
    credits: int
    department_id: int | None = None
    department_name: str | None = None
    created_at: datetime
    updated_at: datetime
