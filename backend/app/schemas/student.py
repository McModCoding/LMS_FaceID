from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models.student import StudentStatus


class StudentCreate(BaseModel):
    student_code: str = Field(..., min_length=1, max_length=50)
    full_name: str = Field(..., min_length=1, max_length=255)
    email: EmailStr
    department_id: int | None = None
    admin_class: str | None = None
    dob: date | None = None
    gender: str | None = None
    phone: str | None = None
    status: StudentStatus = StudentStatus.studying

class StudentUpdate(BaseModel):
    full_name: str | None = None
    email: EmailStr | None = None
    department_id: int | None = None
    admin_class: str | None = None
    dob: date | None = None
    gender: str | None = None
    phone: str | None = None
    status: StudentStatus | None = None
    is_active: bool | None = None

class StudentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    student_code: str
    full_name: str
    email: str | None = None
    department_id: int | None = None
    department_name: str | None = None
    admin_class: str | None = None
    dob: date | None = None
    gender: str | None = None
    phone: str | None = None
    status: StudentStatus
    is_deleted: bool
    user_is_active: bool = True
    created_at: datetime

class StudentWithPasswordResponse(BaseModel):
    student: StudentRead
    temp_password: str

class StudentImportPreviewResponse(BaseModel):
    valid_rows: list[dict]
    warning_rows: list[dict]
    error_rows: list[dict]
    total_rows: int
    valid_count: int
    warning_count: int
    error_count: int

class StudentImportConfirmRequest(BaseModel):
    valid_rows: list[dict]

class StudentPaginatedResponse(BaseModel):
    items: list[StudentRead]
    total: int
    page: int
    page_size: int
