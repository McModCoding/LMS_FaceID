from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class DepartmentCreate(BaseModel):
    code: str = Field(..., min_length=2, max_length=20)
    name: str = Field(..., min_length=2, max_length=255)


class DepartmentUpdate(BaseModel):
    name: str | None = Field(None, min_length=2, max_length=255)
    is_active: bool | None = None


class DepartmentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str
    name: str
    is_active: bool
    created_at: datetime
    updated_at: datetime

