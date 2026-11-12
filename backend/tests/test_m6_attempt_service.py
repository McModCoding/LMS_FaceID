from datetime import datetime, timedelta
from decimal import Decimal

import pytest
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.class_ import ClassStudent, ClassStudentStatus
from app.models.exam import Exam, ExamStatus
from app.models.exam_attempt import AttemptStatus, ExamAttempt
from app.models.student import Student
from app.services.exam_attempt_service import (
    auto_submit_overdue,
    begin_attempt,
    read_attempt,
    save_answer,
    submit_attempt,
)
from app.utils.clock import VN_TZ, override_clock
from tests.test_m4_m5 import _learning_data, _token
from tests.test_m6_exam_drafts import _draft, _question
from tests.test_m6_question_bank import _payload


def test_attempt_resume_access_timeout_and_saved_answers(test_client, db_session):
    cls, lecturer, user = _learning_data(db_session)
    _, _, other = _learning_data(db_session)
    question_id = _question(test_client, cls.subject_id, lecturer, "Câu kiểm tra")
    payload = _draft([question_id])
    payload["max_attempts"] = 1
    created = test_client.post(f"/api/v1/classes/{cls.id}/exams", headers=_token(lecturer), json=payload)
    assert created.status_code == 201
    exam = db_session.get(Exam, created.json()["id"])
    exam.status = ExamStatus.published  # No public publish route exists yet.
    db_session.commit()
    opened = datetime(2026, 10, 20, 8, tzinfo=VN_TZ)
    with override_clock(opened):
        attempt = begin_attempt(db_session, user, exam.id)
        first = read_attempt(db_session, user, attempt.id)
        assert begin_attempt(db_session, user, exam.id).id == attempt.id
        assert "is_correct" not in str(first)
        option = first["questions"][0]["options"][0]["id"]
        save_answer(db_session, user, attempt.id, question_id, [option], None)
        assert read_attempt(db_session, user, attempt.id)["questions"][0]["selected_option_ids"] == [option]
        with pytest.raises(HTTPException) as exc:
            read_attempt(db_session, other, attempt.id)
        assert exc.value.status_code == 403
    student = db_session.query(Student).filter_by(user_id=user.id).one()
    enrollment = db_session.query(ClassStudent).filter_by(class_id=cls.id, student_id=student.id).one()
    enrollment.status = ClassStudentStatus.dropped
    db_session.commit()
    with override_clock(opened + timedelta(minutes=2)), pytest.raises(HTTPException) as exc:
        read_attempt(db_session, user, attempt.id)
    assert exc.value.status_code == 403
    enrollment.status = ClassStudentStatus.enrolled
    db_session.commit()
    with override_clock(opened + timedelta(minutes=60, seconds=5)):
        save_answer(db_session, user, attempt.id, question_id, [option], None)
    with override_clock(opened + timedelta(minutes=60, seconds=5, microseconds=1)):
        with pytest.raises(HTTPException) as exc:
            save_answer(db_session, user, attempt.id, question_id, [option], None)
        assert exc.value.detail["code"] == "ATTEMPT_EXPIRED"
        db_session.expire_all()
        finished = db_session.get(ExamAttempt, attempt.id)
        assert finished.status == AttemptStatus.graded
        assert finished.is_auto_submitted is True
        with pytest.raises(HTTPException) as exc:
            begin_attempt(db_session, user, exam.id)
        assert exc.value.detail["code"] == "MAX_ATTEMPTS"


def test_start_window_and_manual_submit(test_client, db_session):
    cls, lecturer, user = _learning_data(db_session)
    qid = _question(test_client, cls.subject_id, lecturer, "Câu mới")
    response = test_client.post(f"/api/v1/classes/{cls.id}/exams", headers=_token(lecturer), json=_draft([qid]))
    exam = db_session.get(Exam, response.json()["id"])
    exam.status = ExamStatus.published
    db_session.commit()
    opening = datetime(2026, 10, 20, 8, tzinfo=VN_TZ)
    with override_clock(opening - timedelta(seconds=1)), pytest.raises(HTTPException) as exc:
        begin_attempt(db_session, user, exam.id)
    assert exc.value.detail["code"] == "EXAM_CLOSED"
    with override_clock(opening):
        attempt = begin_attempt(db_session, user, exam.id)
        submitted = submit_attempt(db_session, user, attempt.id)
        assert submitted.status == AttemptStatus.graded
        assert submitted.score == 0
        assert submitted.is_auto_submitted is False


def test_periodic_auto_submit_keeps_essay_for_manual_grading(test_client, db_session):
    cls, lecturer, user = _learning_data(db_session)
    payload = _payload("essay")
    payload["options"] = []
    question = test_client.post(f"/api/v1/subjects/{cls.subject_id}/questions", headers=_token(lecturer), json=payload)
    assert question.status_code == 201
    question_id = question.json()["id"]
    result = test_client.post(f"/api/v1/classes/{cls.id}/exams", headers=_token(lecturer), json=_draft([question_id]))
    exam = db_session.get(Exam, result.json()["id"])
    exam.status = ExamStatus.published
    db_session.commit()
    opening = datetime(2026, 10, 20, 8, tzinfo=VN_TZ)
    with override_clock(opening):
        attempt = begin_attempt(db_session, user, exam.id)
        save_answer(db_session, user, attempt.id, question_id, None, "Câu trả lời của tôi")
    with override_clock(opening + timedelta(minutes=60, seconds=5)):
        auto_submit_overdue(db_session)
        db_session.refresh(attempt)
        assert attempt.status == AttemptStatus.in_progress
    with override_clock(opening + timedelta(minutes=60, seconds=5, microseconds=1)):
        assert auto_submit_overdue(db_session) >= 1
        assert auto_submit_overdue(db_session) == 0
        db_session.expire_all()
        assert db_session.get(ExamAttempt, attempt.id).status == AttemptStatus.auto_submitted
        view = read_attempt(db_session, user, attempt.id)
        assert view["questions"][0]["essay_text"] == "Câu trả lời của tôi"


def test_withdrawal_is_not_hidden_by_repeatable_read(test_client, db_session, test_engine):
    cls, lecturer, user = _learning_data(db_session)
    qid = _question(test_client, cls.subject_id, lecturer, "Kiểm tra rút lớp")
    response = test_client.post(f"/api/v1/classes/{cls.id}/exams", headers=_token(lecturer), json=_draft([qid]))
    exam_id = response.json()["id"]
    exam = db_session.get(Exam, exam_id)
    exam.status = ExamStatus.published
    db_session.commit()
    student = db_session.query(Student).filter_by(user_id=user.id).one()
    rr_engine = test_engine.execution_options(isolation_level="REPEATABLE READ")
    with Session(rr_engine) as stale:
        # Establish an old consistent read view before the withdrawal commits.
        assert stale.get(Exam, exam_id) is not None
        enrollment = db_session.query(ClassStudent).filter_by(class_id=cls.id, student_id=student.id).one()
        enrollment.status = ClassStudentStatus.dropped
        db_session.commit()
        with override_clock(datetime(2026, 10, 20, 8, tzinfo=VN_TZ)), pytest.raises(HTTPException) as exc:
            begin_attempt(stale, user, exam_id)
        assert exc.value.status_code == 403


def test_attempt_limit_is_current_under_repeatable_read(test_client, db_session, test_engine):
    cls, lecturer, user = _learning_data(db_session)
    qid = _question(test_client, cls.subject_id, lecturer, "Số lượt làm")
    payload = _draft([qid])
    payload["max_attempts"] = 1
    response = test_client.post(f"/api/v1/classes/{cls.id}/exams", headers=_token(lecturer), json=payload)
    exam_id = response.json()["id"]
    exam = db_session.get(Exam, exam_id)
    exam.status = ExamStatus.published
    db_session.commit()
    opening = datetime(2026, 10, 20, 8, tzinfo=VN_TZ)
    with Session(test_engine.execution_options(isolation_level="REPEATABLE READ")) as stale:
        assert stale.get(Exam, exam_id) is not None
        with override_clock(opening):
            first = begin_attempt(db_session, user, exam_id)
            submit_attempt(db_session, user, first.id)
            with pytest.raises(HTTPException) as exc:
                begin_attempt(stale, user, exam_id)
            assert exc.value.detail["code"] == "MAX_ATTEMPTS"


def test_attempt_score_column_supports_sum_of_allowed_points(test_client, db_session):
    cls, lecturer, user = _learning_data(db_session)
    qid = _question(test_client, cls.subject_id, lecturer, "Kiểm tra sức chứa điểm")
    response = test_client.post(f"/api/v1/classes/{cls.id}/exams", headers=_token(lecturer), json=_draft([qid]))
    exam = db_session.get(Exam, response.json()["id"])
    exam.status = ExamStatus.published
    db_session.commit()
    with override_clock(datetime(2026, 10, 20, 8, tzinfo=VN_TZ)):
        attempt = begin_attempt(db_session, user, exam.id)
        attempt.score = Decimal("49999999999.95000000")
        db_session.commit()
        db_session.expire_all()
        assert db_session.get(ExamAttempt, attempt.id).score == Decimal("49999999999.95000000")
