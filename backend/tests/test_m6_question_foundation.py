"""M6.1: question-bank persistence and migration foundation."""

import pytest
from sqlalchemy import inspect

from app.models.question import Question, QuestionDifficulty, QuestionOption, QuestionType
from app.models.subject import Subject
from app.models.user import User


def test_question_tables_exist_after_schema_setup(db_session):
    inspector = inspect(db_session.bind)
    assert inspector.has_table("questions")
    assert inspector.has_table("question_options")
    assert {"subject_id", "created_by", "type", "content", "difficulty", "explanation"}.issubset(
        {column["name"] for column in inspector.get_columns("questions")}
    )
    assert {"question_id", "content", "is_correct", "order_no"}.issubset(
        {column["name"] for column in inspector.get_columns("question_options")}
    )


@pytest.mark.parametrize("question_type", list(QuestionType))
def test_question_types_persist_with_subject_and_author(db_session, admin_headers, question_type):
    author = db_session.query(User).filter_by(username="admin").one()
    subject = Subject(code=f"M61-{question_type.value}", name="Môn kiểm thử M6", credits=3)
    db_session.add(subject)
    db_session.flush()
    question = Question(
        subject_id=subject.id,
        created_by=author.id,
        type=question_type,
        content="Nội dung câu hỏi kiểm thử",
        difficulty=QuestionDifficulty.medium,
    )
    if question_type != QuestionType.essay:
        question.options = [
            QuestionOption(content="Lựa chọn A", is_correct=True, order_no=1),
            QuestionOption(content="Lựa chọn B", is_correct=False, order_no=2),
        ]
    db_session.add(question)
    db_session.flush()
    question_id = question.id
    db_session.expire_all()
    stored = db_session.get(Question, question_id)
    assert stored.type == question_type
    assert stored.subject_id == subject.id
    assert stored.created_by == author.id
    assert len(stored.options) == (0 if question_type == QuestionType.essay else 2)
