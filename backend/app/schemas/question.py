from datetime import datetime

from pydantic import BaseModel, Field, field_validator, model_validator

from app.models.question import QuestionDifficulty, QuestionType


class QuestionOptionIn(BaseModel):
    content: str = Field(min_length=1, max_length=10000)
    is_correct: bool = False

    @field_validator("content")
    @classmethod
    def clean_content(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Nội dung đáp án không được để trống")
        return value


class QuestionIn(BaseModel):
    type: QuestionType
    content: str = Field(min_length=1, max_length=10000)
    difficulty: QuestionDifficulty = QuestionDifficulty.medium
    explanation: str | None = Field(default=None, max_length=10000)
    options: list[QuestionOptionIn] = Field(default_factory=list, max_length=6)

    @field_validator("content")
    @classmethod
    def clean_content(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Nội dung câu hỏi không được để trống")
        return value

    @model_validator(mode="after")
    def validate_options(self):
        count = len(self.options)
        correct = sum(option.is_correct for option in self.options)
        if self.type == QuestionType.essay:
            if count:
                raise ValueError("Câu tự luận không có đáp án lựa chọn")
        elif count < 2:
            raise ValueError("Câu trắc nghiệm cần từ 2 đến 6 đáp án")
        elif self.type == QuestionType.true_false and (count != 2 or correct != 1):
            raise ValueError("Câu đúng/sai cần 2 lựa chọn và 1 đáp án đúng")
        elif self.type == QuestionType.single and correct != 1:
            raise ValueError("Câu một đáp án cần đúng 1 đáp án đúng")
        elif self.type == QuestionType.multiple and correct < 1:
            raise ValueError("Câu nhiều đáp án cần ít nhất 1 đáp án đúng")
        return self


class QuestionOptionOut(QuestionOptionIn):
    id: int
    order_no: int
    model_config = {"from_attributes": True}


class QuestionOut(BaseModel):
    id: int
    subject_id: int
    created_by: int
    type: QuestionType
    content: str
    difficulty: QuestionDifficulty
    explanation: str | None
    options: list[QuestionOptionOut]
    created_at: datetime
    can_edit: bool


class QuestionList(BaseModel):
    items: list[QuestionOut]
    total: int
    page: int
    page_size: int


class QuestionImportIn(BaseModel):
    items: list[QuestionIn] = Field(min_length=1, max_length=500)
