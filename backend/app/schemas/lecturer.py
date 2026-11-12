from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models.lecturer import LecturerType


class LecturerCreate(BaseModel):
    code: str = Field(..., min_length=1, max_length=50)
    full_name: str = Field(..., min_length=1, max_length=255)
    email: EmailStr
    department_id: int | None = None
    phone: str | None = None
    degree: str | None = None
    department: str | None = None
    type: LecturerType = LecturerType.full_time

class LecturerUpdate(BaseModel):
    full_name: str | None = None
    email: EmailStr | None = None
    department_id: int | None = None
    phone: str | None = None
    degree: str | None = None
    department: str | None = None
    type: LecturerType | None = None
    is_active: bool | None = None

class LecturerRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    code: str
    full_name: str
    email: str | None = None
    department_id: int | None = None
    department_name: str | None = None
    phone: str | None = None
    degree: str | None = None
    department: str | None = None
    type: LecturerType
    is_deleted: bool
    user_is_active: bool = True
    created_at: datetime

class LecturerWithPasswordResponse(BaseModel):
    lecturer: LecturerRead
    temp_password: str

class LecturerPaginatedResponse(BaseModel):
    items: list[LecturerRead]
    total: int
    page: int
    page_size: int
