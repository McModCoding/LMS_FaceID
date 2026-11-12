"""Exercise the unreleased router in an isolated test app, never the live app."""

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from threading import Barrier

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.deps import get_db
from app.main import app
from app.models.class_ import ClassStudent, ClassStudentStatus
from app.models.exam import Exam
from app.models.exam_attempt import AttemptAnswer, ExamAttempt
from app.models.student import Student
from app.models.user import User
from app.routers.exam_attempts import router
from app.services.exam_attempt_service import (
    begin_attempt,
    read_attempt,
    save_answer,
    submit_attempt,
)
from app.utils.clock import VN_TZ, override_clock
from tests.test_m4_m5 import _learning_data, _token
from tests.test_m6_exam_drafts import _draft, _question


@pytest.fixture
def attempt_client(TestingSessionLocal):
    isolated = FastAPI()
    isolated.include_router(router, prefix="/api/v1")

    def test_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    isolated.dependency_overrides[get_db] = test_db
    with TestClient(isolated) as client:
        yield client


def _exam(test_client, db, *, max_attempts=1):
    cls, lecturer, student = _learning_data(db)
    qid = _question(test_client, cls.subject_id, lecturer, "Câu hỏi thử hợp đồng")
    payload = _draft([qid])
    payload["max_attempts"] = max_attempts
    response = test_client.post(f"/api/v1/classes/{cls.id}/exams", headers=_token(lecturer), json=payload)
    assert response.status_code == 201
    exam = db.get(Exam, response.json()["id"])
    with override_clock(datetime(2026, 10, 19, 12, tzinfo=VN_TZ)):
        published = test_client.post(f"/api/v1/exams/{exam.id}/publish", headers=_token(lecturer))
        assert published.status_code == 200, published.text
    return cls, lecturer, student, exam.id, qid


def test_attempt_and_publish_apis_are_mounted():
    paths = app.openapi()["paths"]
    assert "/api/v1/exams/{exam_id}/attempts" in paths
    assert "/api/v1/attempts/{attempt_id}" in paths
    assert "/api/v1/classes/{class_id}/student-exams" in paths
    assert "/api/v1/exams/{exam_id}/publish" in paths


def test_student_exam_list_only_returns_published_exams_and_own_attempts(
    test_client, attempt_client, db_session
):
    cls, lecturer, student, published_id, _ = _exam(test_client, db_session, max_attempts=2)
    draft_response = test_client.post(
        f"/api/v1/classes/{cls.id}/exams", headers=_token(lecturer), json=_draft([])
    )
    assert draft_response.status_code == 201
    _, _, other = _learning_data(db_session)
    url = f"/api/v1/classes/{cls.id}/student-exams"
    assert attempt_client.get(url, headers=_token(lecturer)).status_code == 403
    assert attempt_client.get(url, headers=_token(other)).status_code == 403
    with override_clock(datetime(2026, 10, 19, 12, tzinfo=VN_TZ)):
        response = attempt_client.get(url, headers=_token(student))
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["total"] == 1
    exam = payload["items"][0]
    assert exam["id"] == published_id
    assert exam["status"] == "upcoming"
    assert exam["used_attempts"] == 0
    assert "show_result" not in response.text and "score" not in response.text
    opening = datetime(2026, 10, 20, 8, tzinfo=VN_TZ)
    with override_clock(opening):
        available = attempt_client.get(url, headers=_token(student)).json()["items"][0]
        assert available["status"] == "available"
        attempt = attempt_client.post(f"/api/v1/exams/{published_id}/attempts", headers=_token(student))
        assert attempt.status_code == 200, attempt.text
        active = attempt_client.get(url, headers=_token(student)).json()["items"][0]
        assert active["status"] == "in_progress"
        assert active["active_attempt_id"] == attempt.json()["id"]
        submitted = attempt_client.post(f"/api/v1/attempts/{attempt.json()['id']}/submit", headers=_token(student))
        assert submitted.status_code == 200, submitted.text
        assert "score" not in submitted.text and "is_correct" not in submitted.text
        retry = attempt_client.get(url, headers=_token(student)).json()["items"][0]
        assert retry["status"] == "retry_available"
        assert retry["used_attempts"] == 1


def test_attempt_contract_resume_timeout_and_permissions(test_client, attempt_client, db_session):
    cls, lecturer, student, exam_id, qid = _exam(test_client, db_session)
    _, _, other = _learning_data(db_session)
    url = f"/api/v1/exams/{exam_id}/attempts"
    opening = datetime(2026, 10, 20, 8, tzinfo=VN_TZ)
    assert attempt_client.post(url).status_code == 401
    with override_clock(opening):
        assert attempt_client.post(url, headers=_token(lecturer)).status_code == 403
        assert attempt_client.post(url, headers=_token(other)).status_code == 403
        response = attempt_client.post(url, headers=_token(student))
        assert response.status_code == 200, response.text
        data = response.json()
        assert data["exam_id"] == exam_id
        assert data["started_at"] == "2026-10-20T01:00:00Z"
        assert data["deadline_at"] == "2026-10-20T02:00:00Z"
        assert data["server_now"] == "2026-10-20T01:00:00Z"
        assert "is_correct" not in response.text and "explanation" not in response.text
        assert "score" not in data
        attempt_id = data["id"]
        assert attempt_client.post(url, headers=_token(student)).json()["id"] == attempt_id
        assert attempt_client.get(f"/api/v1/attempts/{attempt_id}", headers=_token(other)).status_code == 403
        answer_url = f"/api/v1/attempts/{attempt_id}/answers/{qid}"
        option = data["questions"][0]["options"][0]["id"]
        assert attempt_client.put(answer_url, headers=_token(student), json={"selected_option_ids": [option]}).status_code == 204
        assert attempt_client.get(f"/api/v1/attempts/{attempt_id}", headers=_token(student)).json()["questions"][0]["selected_option_ids"] == [option]
        assert attempt_client.put(answer_url, headers=_token(student), json={"selected_option_ids": [option, option]}).status_code == 422
        assert attempt_client.put(answer_url, headers=_token(student), json={"selected_option_ids": [True]}).status_code == 422
        assert attempt_client.put(answer_url, headers=_token(student), json={"score": 10}).status_code == 422
        assert attempt_client.put(answer_url, headers=_token(student), json={"essay_text": "x" * 65536}).status_code == 422
        assert attempt_client.put(f"/api/v1/attempts/{attempt_id}/answers/99999999", headers=_token(student), json={}).status_code == 404
    student_record = db_session.query(Student).filter_by(user_id=student.id).one()
    enrollment = db_session.query(ClassStudent).filter_by(class_id=cls.id, student_id=student_record.id).one()
    enrollment.status = ClassStudentStatus.dropped
    db_session.commit()
    with override_clock(opening + timedelta(minutes=1)):
        assert attempt_client.get(f"/api/v1/attempts/{attempt_id}", headers=_token(student)).status_code == 403
        assert attempt_client.put(answer_url, headers=_token(student), json={}).status_code == 403
    db_session.expire_all()
    assert db_session.query(AttemptAnswer).filter_by(attempt_id=attempt_id, question_id=qid).one().selected_option_ids == [option]
    enrollment = db_session.query(ClassStudent).filter_by(class_id=cls.id, student_id=student_record.id).one()
    enrollment.status = ClassStudentStatus.enrolled
    db_session.commit()
    with override_clock(opening + timedelta(minutes=60, seconds=5)):
        assert attempt_client.put(answer_url, headers=_token(student), json={"selected_option_ids": [option]}).status_code == 204
    with override_clock(opening + timedelta(minutes=60, seconds=5, microseconds=1)):
        assert attempt_client.put(answer_url, headers=_token(student), json={}).status_code == 409
        result = attempt_client.get(f"/api/v1/attempts/{attempt_id}", headers=_token(student)).json()
        assert result["status"] == "graded"
        assert result["questions"][0]["selected_option_ids"] == [option]


def test_repeatable_read_observes_saved_answer(test_client, db_session, test_engine):
    _, _, student, exam_id, qid = _exam(test_client, db_session)
    opening = datetime(2026, 10, 20, 8, tzinfo=VN_TZ)
    with override_clock(opening):
        attempt_id = begin_attempt(db_session, student, exam_id).id
        option = read_attempt(db_session, student, attempt_id)["questions"][0]["options"][0]["id"]
        with Session(test_engine.execution_options(isolation_level="REPEATABLE READ")) as stale:
            assert stale.get(ExamAttempt, attempt_id) is not None
            save_answer(db_session, student, attempt_id, qid, [option], None)
            assert read_attempt(stale, student, attempt_id)["questions"][0]["selected_option_ids"] == [option]
        submit_attempt(db_session, student, attempt_id)


def test_simultaneous_starts_resume_one_attempt(test_client, db_session, test_engine):
    _, _, student, exam_id, _ = _exam(test_client, db_session)
    student_id = student.id
    barrier = Barrier(2, timeout=20)

    def start():
        with Session(test_engine) as session:
            user = session.get(User, student_id)
            barrier.wait()
            return begin_attempt(session, user, exam_id).id

    with override_clock(datetime(2026, 10, 20, 8, tzinfo=VN_TZ)), ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(start) for _ in range(2)]
        attempt_ids = [future.result(timeout=30) for future in futures]
        submit_attempt(db_session, student, attempt_ids[0])
    assert attempt_ids[0] == attempt_ids[1]
    assert db_session.query(ExamAttempt).filter_by(exam_id=exam_id).count() == 1


def test_expired_attempt_is_finalized_before_next_start(test_client, attempt_client, db_session):
    _, _, student, exam_id, _ = _exam(test_client, db_session, max_attempts=2)
    opening = datetime(2026, 10, 20, 8, tzinfo=VN_TZ)
    url = f"/api/v1/exams/{exam_id}/attempts"
    with override_clock(opening):
        first = attempt_client.post(url, headers=_token(student)).json()
    with override_clock(opening + timedelta(minutes=60, seconds=6)):
        response = attempt_client.post(url, headers=_token(student))
        assert response.status_code == 200, response.text
        second = response.json()
        assert second["id"] != first["id"]
        assert second["attempt_no"] == 2
        assert second["status"] == "in_progress"
        submit_url = f"/api/v1/attempts/{second['id']}/submit"
        submitted = attempt_client.post(submit_url, headers=_token(student))
        assert submitted.status_code == 200
        assert "score" not in submitted.json()
        assert attempt_client.post(submit_url, headers=_token(student)).status_code == 409
    db_session.expire_all()
    first_row = db_session.get(ExamAttempt, first["id"])
    assert first_row.is_auto_submitted is True
    assert first_row.status.value == "graded"


def test_expired_attempt_persists_when_no_retry_remains(test_client, attempt_client, db_session):
    _, _, student, exam_id, _ = _exam(test_client, db_session, max_attempts=1)
    opening = datetime(2026, 10, 20, 8, tzinfo=VN_TZ)
    url = f"/api/v1/exams/{exam_id}/attempts"
    with override_clock(opening):
        attempt_id = attempt_client.post(url, headers=_token(student)).json()["id"]
    with override_clock(opening + timedelta(minutes=60, seconds=6)):
        response = attempt_client.post(url, headers=_token(student))
        assert response.status_code == 409
        assert response.json()["detail"]["code"] == "MAX_ATTEMPTS"
    db_session.expire_all()
    attempt = db_session.get(ExamAttempt, attempt_id)
    assert attempt.is_auto_submitted is True
    assert attempt.status.value == "graded"


def test_simultaneous_saves_do_not_duplicate_answers(test_client, db_session, test_engine):
    _, _, student, exam_id, qid = _exam(test_client, db_session)
    opening = datetime(2026, 10, 20, 8, tzinfo=VN_TZ)
    with override_clock(opening):
        attempt_id = begin_attempt(db_session, student, exam_id).id
        options = [item["id"] for item in read_attempt(db_session, student, attempt_id)["questions"][0]["options"]]
        db_session.rollback()  # Release the read's locks before testing concurrent requests.
        student_id = student.id
        barrier = Barrier(2, timeout=20)
        rr_engine = test_engine.execution_options(isolation_level="REPEATABLE READ")

        def save(option):
            with Session(rr_engine) as session:
                user = session.get(User, student_id)
                barrier.wait()
                save_answer(session, user, attempt_id, qid, [option], None)

        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(save, option) for option in options]
            for future in futures:
                future.result(timeout=30)
        db_session.expire_all()
        answers = db_session.query(AttemptAnswer).filter_by(attempt_id=attempt_id, question_id=qid).all()
        assert len(answers) == 1
        assert answers[0].selected_option_ids in [[option] for option in options]
        submit_attempt(db_session, student, attempt_id)
