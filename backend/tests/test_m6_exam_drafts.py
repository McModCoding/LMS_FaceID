from uuid import uuid4

from app.models.audit import AuditLog
from app.models.class_ import ClassStatus
from app.models.exam import Exam, ExamStatus
from tests.test_m4_m5 import _admin, _learning_data, _token
from tests.test_m6_question_bank import _payload, _second_lecturer


def _draft(question_ids=()):
    return {"title": "Bài kiểm tra nháp", "description": "Thông tin đề", "duration_min": 60,
        "open_at": "2026-10-20T08:00:00+07:00", "close_at": "2026-10-20T10:00:00+07:00",
        "shuffle_questions": True, "shuffle_options": False, "max_attempts": 2,
        "score_policy": "highest", "show_result": "after_close", "require_fullscreen": True,
        "record_events": True, "violation_types": ["tab_hidden", "fullscreen_exit"],
        "max_violations": 3, "auto_submit_on_violation": True,
        "questions": [{"question_id": qid, "points": "2.5"} for qid in question_ids]}


def _question(client, subject_id, user, content):
    payload = _payload()
    payload["content"] = content
    response = client.post(f"/api/v1/subjects/{subject_id}/questions", json=payload, headers=_token(user))
    assert response.status_code == 201, response.text
    return response.json()["id"]


def test_draft_crud_and_class_permission(test_client, db_session):
    cls, lecturer, student = _learning_data(db_session)
    other = _second_lecturer(db_session, cls)
    admin = _admin(db_session, uuid4().hex[:8])
    question1 = _question(test_client, cls.subject_id, lecturer, "Một")
    question2 = _question(test_client, cls.subject_id, lecturer, "Hai")
    base = f"/api/v1/classes/{cls.id}/exams"
    assert test_client.get(base, headers=_token(student)).status_code == 403
    assert test_client.post(base, headers=_token(other), json=_draft()).status_code == 403
    result = test_client.post(base, headers=_token(lecturer), json=_draft([question1, question2]))
    assert result.status_code == 201, result.text
    exam = result.json()
    assert exam["status"] == "draft"
    assert exam["open_at"] == "2026-10-20T01:00:00Z"
    assert [q["question_id"] for q in exam["questions"]] == [question1, question2]
    assert test_client.get(base, headers=_token(admin)).json()["total"] == 1
    assert test_client.delete(f"/api/v1/questions/{question1}", headers=_token(lecturer)).status_code == 409
    changed_question = _payload()
    changed_question["content"] = "Đã sửa trong ngân hàng"
    assert test_client.put(f"/api/v1/questions/{question1}", headers=_token(lecturer), json=changed_question).status_code == 200
    assert test_client.get(base, headers=_token(lecturer)).json()["items"][0]["questions"][0]["content"] == "Đã sửa trong ngân hàng"
    edited = _draft([question2, question1])
    edited["questions"][0]["points"] = "3.125"
    response = test_client.put(f"/api/v1/exams/{exam['id']}", headers=_token(lecturer), json=edited)
    assert response.status_code == 200, response.text
    assert response.json()["questions"][0]["question_id"] == question2
    assert response.json()["questions"][0]["points"] == "3.1250"
    assert test_client.delete(f"/api/v1/exams/{exam['id']}", headers=_token(admin)).status_code == 204
    assert test_client.delete(f"/api/v1/questions/{question1}", headers=_token(lecturer)).status_code == 204
    actions = {row.action for row in db_session.query(AuditLog).filter(
        AuditLog.entity == "exams", AuditLog.entity_id == str(exam["id"])).all()}
    assert {"CREATE_EXAM_DRAFT", "UPDATE_EXAM_DRAFT", "DELETE_EXAM_DRAFT"}.issubset(actions)


def test_invalid_draft_and_foreign_subject(test_client, db_session):
    cls, lecturer, _ = _learning_data(db_session)
    other_cls, other_lecturer, _ = _learning_data(db_session)
    other_question = _question(test_client, other_cls.subject_id, other_lecturer, "Môn khác")
    base = f"/api/v1/classes/{cls.id}/exams"
    assert test_client.post(base, headers=_token(lecturer), json=_draft([other_question])).status_code == 422
    for changes in [
        {"close_at": "2026-10-20T07:00:00+07:00"},
        {"open_at": "2026-10-20T08:00:00"},
        {"duration_min": 0}, {"max_attempts": 0},
        {"require_fullscreen": False}, {"max_violations": 0},
        {"record_events": False},
    ]:
        payload = _draft()
        payload.update(changes)
        assert test_client.post(base, headers=_token(lecturer), json=payload).status_code == 422
    assert test_client.get(base, headers=_token(lecturer)).json()["total"] == 0
    db_session.refresh(cls)
    cls.status = ClassStatus.closed
    db_session.commit()
    assert test_client.post(base, headers=_token(lecturer), json=_draft()).status_code == 409


def test_draft_cannot_be_published_via_input_or_edited_after_status_change(test_client, db_session):
    cls, lecturer, _ = _learning_data(db_session)
    payload = _draft()
    payload["status"] = "published"
    result = test_client.post(f"/api/v1/classes/{cls.id}/exams", headers=_token(lecturer), json=payload)
    assert result.status_code == 201
    exam_id = result.json()["id"]
    assert result.json()["status"] == "draft"
    assert test_client.post(f"/api/v1/exams/{exam_id}/publish", headers=_token(lecturer)).status_code == 409
    exam = db_session.get(Exam, exam_id)
    exam.status = ExamStatus.published
    db_session.commit()
    assert test_client.put(f"/api/v1/exams/{exam_id}", headers=_token(lecturer), json=_draft()).status_code == 409
    assert test_client.delete(f"/api/v1/exams/{exam_id}", headers=_token(lecturer)).status_code == 409
