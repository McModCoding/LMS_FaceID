from datetime import datetime

from pydantic import BaseModel, Field, field_validator


class MaterialUpdate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=5000)

    @field_validator("title", "description", mode="before")
    @classmethod
    def strip_text(cls, value):
        return value.strip() if isinstance(value, str) else value


class MaterialOut(BaseModel):
    id: int
    class_id: int
    title: str
    description: str | None
    url: str | None
    filename: str | None
    has_file: bool
    created_at: datetime


class MaterialList(BaseModel):
    items: list[MaterialOut]
    total: int
    page: int
    page_size: int
