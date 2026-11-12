from decimal import Decimal

import pytest
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.exam import Exam, ExamStatus
from app.services.exam_content_service import (
    freeze_exam_content,
    score_answer,
    shuffled_ids,
    student_question,
)
from tests.test_m4_m5 import _learning_data, _token
from tests.test_m6_exam_drafts import _draft, _question
from tests.test_m6_question_bank import _payload


def test_snapshot_is_atomic_immutable_and_hides_answers(test_client, db_session):
    cls, lecturer, _ = _learning_data(db_session)
    question_id = _question(test_client, cls.subject_id, lecturer, "Nội dung ban đầu")
    result = test_client.post(f"/api/v1/classes/{cls.id}/exams", headers=_token(lecturer), json=_draft([question_id]))
    assert result.status_code == 201
    exam = db_session.get(Exam, result.json()["id"])
    with pytest.raises(HTTPException):
        freeze_exam_content(db_session, exam.id)
    exam.status = ExamStatus.published
    db_session.commit()
    frozen = freeze_exam_content(db_session, exam.id)
    assert frozen[0]["content"] == "Nội dung ban đầu"
    assert frozen[0]["options"][0]["is_correct"] is True
    public = student_question(frozen[0])
    assert "explanation" not in public
    assert all("is_correct" not in option for option in public["options"])
    db_session.rollback()
    db_session.expire_all()
    assert db_session.get(Exam, exam.id).questions[0].frozen_content is None
    frozen = freeze_exam_content(db_session, exam.id)
    db_session.commit()
    updated = _payload()
    updated["content"] = "Nội dung đã sửa"
    response = test_client.put(f"/api/v1/questions/{question_id}", headers=_token(lecturer), json=updated)
    assert response.status_code == 200
    db_session.expire_all()
    assert freeze_exam_content(db_session, exam.id) == frozen
    assert frozen[0]["content"] == "Nội dung ban đầu"


def test_fisher_yates_reproducible_and_nonmutating():
    original = list(range(25))
    assert shuffled_ids(original, 42) == shuffled_ids(original, 42)
    assert sorted(shuffled_ids(original, 42)) == original
    assert original == list(range(25))
    assert shuffled_ids([], 42) == []


def test_scoring_and_invalid_choices():
    base = {"type": "multiple", "points": "3.0000", "options": [
        {"id": 1, "is_correct": True}, {"id": 2, "is_correct": True},
        {"id": 3, "is_correct": False}, {"id": 4, "is_correct": False}]}
    assert score_answer(base, [1]) == Decimal("1.5")
    assert score_answer(base, [1, 2]) == Decimal("3")
    assert score_answer(base, [1, 3]) == Decimal("0")
    assert score_answer(base, [3, 4]) == Decimal("0")
    assert score_answer(base, []) == Decimal("0")
    with pytest.raises(ValueError):
        score_answer(base, [1, 1])
    with pytest.raises(ValueError):
        score_answer(base, [999])
    single = {**base, "type": "single", "options": base["options"][1:]}
    assert score_answer(single, [2]) == Decimal("3")
    assert score_answer(single, [3]) == Decimal("0")
    with pytest.raises(ValueError):
        score_answer(single, [2, 3])
    assert score_answer({**base, "type": "essay", "options": []}, []) is None


def test_snapshot_reads_current_question_and_options_in_repeatable_read(test_client, db_session, test_engine):
    cls, lecturer, _ = _learning_data(db_session)
    question_id = _question(test_client, cls.subject_id, lecturer, "Bản cũ")
    result = test_client.post(f"/api/v1/classes/{cls.id}/exams", headers=_token(lecturer), json=_draft([question_id]))
    exam_id = result.json()["id"]
    exam = db_session.get(Exam, exam_id)
    exam.status = ExamStatus.published
    db_session.commit()
    with Session(test_engine.execution_options(isolation_level="REPEATABLE READ")) as stale:
        assert stale.get(Exam, exam_id) is not None
        updated = _payload()
        updated["content"] = "Bản mới"
        updated["options"][0]["content"] = "Đáp án mới"
        assert test_client.put(f"/api/v1/questions/{question_id}", headers=_token(lecturer), json=updated).status_code == 200
        frozen = freeze_exam_content(stale, exam_id)
        assert frozen[0]["content"] == "Bản mới"
        assert frozen[0]["options"][0]["content"] == "Đáp án mới"
