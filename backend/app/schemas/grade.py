from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models.grade import GradeType


class GradeComponentIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=200)
    weight: Decimal = Field(ge=0, le=100, max_digits=7, decimal_places=4)
    type: GradeType
    ref_id: int | None = Field(default=None, gt=0)

    @field_validator("name")
    @classmethod
    def clean_name(cls, value):
        value = value.strip()
        if not value:
            raise ValueError("Tên thành phần không được để trống.")
        return value

    @model_validator(mode="after")
    def valid_reference(self):
        if (self.type in ("assignment", "exam")) != (self.ref_id is not None):
            raise ValueError("Bài tập/kiểm tra cần nguồn tham chiếu; chuyên cần/nhập tay không có nguồn tham chiếu.")
        return self


class ManualGradeIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    score: Decimal | None = Field(default=None, ge=0, le=10, max_digits=7, decimal_places=4)


class GradeComponentOut(BaseModel):
    id: int
    name: str
    type: GradeType
    weight: Decimal
    ref_id: int | None
    source_name: str


class GradeValueOut(BaseModel):
    component_id: int
    score: Decimal | None


class GradeRowOut(BaseModel):
    student_id: int
    student_code: str
    student_name: str
    is_dropped: bool
    values: list[GradeValueOut]
    missing_count: int
    total_score: Decimal


class GradebookOut(BaseModel):
    published: bool
    weight_total: Decimal | None
    components: list[GradeComponentOut]
    items: list[GradeRowOut]
    total: int
    page: int
    page_size: int
    message: str
