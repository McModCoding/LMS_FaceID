from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, model_validator

from app.models.class_ import ClassStatus


# ------------------------------------------------------------------ Class
class ClassCreate(BaseModel):
    code: str = Field(..., min_length=1, max_length=50)
    subject_id: int
    semester_id: int
    lecturer_id: int | None = None
    max_students: int = Field(50, ge=1, le=500)
    late_after_min: int = Field(10, ge=0)
    absent_after_min: int = Field(30, ge=1)
    weight_present: float = Field(1.0, ge=0.0, le=1.0)
    weight_late: float = Field(0.5, ge=0.0, le=1.0)
    weight_excused: float = Field(1.0, ge=0.0, le=1.0)
    attendance_warning_absences: int = Field(3, ge=1)

    @model_validator(mode="after")
    def check_late_before_absent(self) -> "ClassCreate":
        if self.late_after_min >= self.absent_after_min:
            raise ValueError("late_after_min phải nhỏ hơn absent_after_min")
        return self


class ClassUpdate(BaseModel):
    lecturer_id: int | None = None
    max_students: int | None = Field(None, ge=1, le=500)
    late_after_min: int | None = Field(None, ge=0)
    absent_after_min: int | None = Field(None, ge=1)
    weight_present: float | None = Field(None, ge=0.0, le=1.0)
    weight_late: float | None = Field(None, ge=0.0, le=1.0)
    weight_excused: float | None = Field(None, ge=0.0, le=1.0)
    attendance_warning_absences: int | None = Field(None, ge=1)

    @model_validator(mode="after")
    def check_late_before_absent(self) -> "ClassUpdate":
        la = self.late_after_min
        aa = self.absent_after_min
        if la is not None and aa is not None and la >= aa:
            raise ValueError("late_after_min phải nhỏ hơn absent_after_min")
        return self


class ClassOut(BaseModel):
    id: int
    code: str
    subject_id: int
    subject_name: str | None = None
    subject_code: str | None = None
    semester_id: int
    semester_name: str | None = None
    lecturer_id: int | None = None
    lecturer_name: str | None = None
    lecturer_code: str | None = None
    max_students: int
    enrolled_count: int = 0
    status: ClassStatus
    late_after_min: int
    absent_after_min: int
    weight_present: float
    weight_late: float
    weight_excused: float
    attendance_warning_absences: int
    created_at: datetime

    model_config = {"from_attributes": True}


class ClassListResponse(BaseModel):
    items: list[ClassOut]
    total: int
    page: int
    page_size: int


# --------------------------------------------------------------- ClassStudent
class EnrollStudentsRequest(BaseModel):
    student_ids: list[int] = Field(..., min_length=1)


class DropStudentRequest(BaseModel):
    pass  # student_id từ path param


class EnrollmentPreviewRow(BaseModel):
    row: int
    student_code: str
    full_name: str | None = None
    status: str  # "ok", "warning", "error"
    reason: str | None = None


class EnrollmentImportPreview(BaseModel):
    valid_rows: list[dict[str, Any]]
    warning_rows: list[dict[str, Any]]
    error_rows: list[dict[str, Any]]
    total_rows: int
    valid_count: int
    warning_count: int
    error_count: int


class EnrollmentImportConfirmRequest(BaseModel):
    valid_rows: list[dict[str, Any]]


class ClassStudentOut(BaseModel):
    id: int
    student_id: int
    student_code: str
    full_name: str
    status: str
    enrolled_at: datetime

    model_config = {"from_attributes": True}


class ClassStudentListResponse(BaseModel):
    items: list[ClassStudentOut]
    total: int
    page: int
    page_size: int
