"""M6 phase 2: exercise real mounted endpoints against isolated MySQL."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from io import BytesIO
from threading import Barrier
from uuid import uuid4

import pytest
from openpyxl import load_workbook
from sqlalchemy.orm import Session

from app.models.class_ import ClassStatus
from app.models.exam import Exam, ExamStatus
from app.models.learning import Notification
from app.models.user import User
from app.schemas.exam_management import ExamEventIn
from app.services import exam_lifecycle_service
from app.services.exam_event_service import record_event
from app.utils.clock import VN_TZ, override_clock
from tests.test_m4_m5 import _learning_data, _token
from tests.test_m6_exam_drafts import _draft

OPEN = datetime(2026, 10, 20, 8, tzinfo=VN_TZ)


def setup_exam(client, db, **changes):
    cls, lecturer, student = _learning_data(db)
    questions = []
    for kind in ("single", "multiple", "true_false", "essay"):
        options = [] if kind == "essay" else [{"content": "Đúng A", "is_correct": True},
            {"content": "Đúng B" if kind == "multiple" else "Sai", "is_correct": kind == "multiple"}]
        if kind == "multiple":
            options.append({"content": "Sai C", "is_correct": False})
        res = client.post(f"/api/v1/subjects/{cls.subject_id}/questions", headers=_token(lecturer),
            json={"type": kind, "content": f"Câu {kind}", "explanation": "Giải thích bí mật", "options": options})
        assert res.status_code == 201, res.text
        questions.append(res.json())
    payload = _draft([q["id"] for q in questions])
    payload.update(shuffle_questions=False, require_fullscreen=False, violation_types=["copy"],
                   show_result="after_submit", max_violations=2)
    payload.update(changes)
    res = client.post(f"/api/v1/classes/{cls.id}/exams", headers=_token(lecturer), json=payload)
    assert res.status_code == 201, res.text
    eid = res.json()["id"]
    with override_clock(OPEN - timedelta(minutes=1)):
        res = client.post(f"/api/v1/exams/{eid}/publish", headers=_token(lecturer))
        assert res.status_code == 200, res.text
    return cls, lecturer, student, eid, questions, payload


def begin(client, student, eid):
    res = client.post(f"/api/v1/exams/{eid}/attempts", headers=_token(student))
    assert res.status_code == 200, res.text
    return res.json()


def answer_and_submit(client, student, attempt, questions):
    for q in questions:
        data = {"essay_text": "Bài làm tự luận."} if q["type"] == "essay" else {
            "selected_option_ids": [o["id"] for o in q["options"] if o["is_correct"]]}
        res = client.put(f"/api/v1/attempts/{attempt['id']}/answers/{q['id']}", headers=_token(student), json=data)
        assert res.status_code == 204, res.text
    res = client.post(f"/api/v1/attempts/{attempt['id']}/submit", headers=_token(student))
    assert res.status_code == 200, res.text
    return res.json()


def test_publication_notifications_snapshot_and_edit_lock(test_client, db_session):
    cls, lecturer, student, eid, questions, payload = setup_exam(test_client, db_session)
    notifications = db_session.query(Notification).filter_by(type="exam_published", user_id=student.id).all()
    assert len(notifications) == 1 and notifications[0].link == f"/student/classes/{cls.id}?tab=exams"
    with override_clock(OPEN):
        assert test_client.post(f"/api/v1/exams/{eid}/publish", headers=_token(lecturer)).status_code == 409
        # A published exam is editable before the first attempt, then frozen again.
        payload["title"] = "Đã chỉnh trước lượt đầu"
        res = test_client.put(f"/api/v1/exams/{eid}", headers=_token(lecturer), json=payload)
        assert res.status_code == 200, res.text
        changed = {k: questions[0][k] for k in ("content", "type", "difficulty", "explanation", "options")}
        changed["content"] = "Ngân hàng đã đổi"
        changed["options"] = [{"content": "Mới", "is_correct": True}, {"content": "Khác", "is_correct": False}]
        assert test_client.put(f"/api/v1/questions/{questions[0]['id']}", headers=_token(lecturer), json=changed).status_code == 200
        attempt = begin(test_client, student, eid)
        assert attempt["questions"][0]["content"] == "Câu single"
        assert "is_correct" not in str(attempt) and "Giải thích bí mật" not in str(attempt)
        assert test_client.put(f"/api/v1/exams/{eid}", headers=_token(lecturer), json=payload).status_code == 409
        listed = test_client.get(f"/api/v1/classes/{cls.id}/exams", headers=_token(lecturer)).json()
        assert listed["items"][0]["has_attempts"] is True
        assert listed["items"][0]["questions"][0]["content"] == "Câu single"
    assert db_session.query(Notification).filter_by(type="exam_published", user_id=student.id).count() == 1


def test_publication_failure_rolls_back_and_empty_past_rejected(test_client, db_session, monkeypatch):
    cls, lecturer, _, _, questions, payload = setup_exam(test_client, db_session)
    eid = test_client.post(f"/api/v1/classes/{cls.id}/exams", headers=_token(lecturer), json=payload).json()["id"]
    count = db_session.query(Notification).count()
    def fail(*args, **kwargs):
        raise RuntimeError("notification storage failure")
    with monkeypatch.context() as patch:
        patch.setattr(exam_lifecycle_service, "notify_enrolled_students", fail)
        with override_clock(OPEN), pytest.raises(RuntimeError):
            exam_lifecycle_service.publish_exam(db_session, lecturer, eid)
    assert db_session.get(Exam, eid).status == ExamStatus.draft
    assert db_session.query(Notification).count() == count
    empty = test_client.post(f"/api/v1/classes/{cls.id}/exams", headers=_token(lecturer), json=_draft()).json()["id"]
    with override_clock(OPEN):
        assert test_client.post(f"/api/v1/exams/{empty}/publish", headers=_token(lecturer)).status_code == 409
    with override_clock(OPEN + timedelta(days=1)):
        assert test_client.post(f"/api/v1/exams/{eid}/publish", headers=_token(lecturer)).status_code == 409


@pytest.mark.parametrize("policy", ["after_submit", "after_close", "never"])
def test_result_policy_manual_grade_statistics_export(test_client, db_session, policy):
    _, lecturer, student, eid, questions, _ = setup_exam(test_client, db_session, show_result=policy)
    with override_clock(OPEN):
        attempt = begin(test_client, student, eid)
        result = answer_and_submit(test_client, student, attempt, questions)
        assert result["status"] == "submitted" and "score" not in result
        aid = attempt["id"]
        qid = questions[-1]["id"]
        url = f"/api/v1/attempts/{aid}/questions/{qid}/grade"
        assert test_client.post(url, headers=_token(student), json={"score": 1}).status_code == 403
        for score in (-1, 3):
            assert test_client.post(url, headers=_token(lecturer), json={"score": score}).status_code == 422
        review = test_client.get(f"/api/v1/attempts/{aid}/review", headers=_token(lecturer)).json()
        assert review["score10"] is None and review["questions"][0]["score"] == "2.50000000"
        response = test_client.post(url, headers=_token(lecturer), json={"score": "2", "feedback": "Có lập luận."})
        assert response.status_code == 200, response.text
        assert response.json()["score10"] == "9.50"
        summary = test_client.get(f"/api/v1/exams/{eid}/results", headers=_token(student)).json()
        assert summary["available"] is (policy == "after_submit")
        assert summary["score10"] == ("9.50" if policy == "after_submit" else None)
        detail = test_client.get(f"/api/v1/attempts/{aid}/result", headers=_token(student))
        assert detail.status_code == (200 if policy == "after_submit" else 403)
        stats = test_client.get(f"/api/v1/exams/{eid}/stats", headers=_token(lecturer)).json()
        assert stats["average"] == "9.50" and stats["pending_grading"] == 0
        assert sum(b["count"] for b in stats["histogram"]) == 1
        assert stats["questions"][0]["correct"] == 1 and stats["questions"][-1]["correct_rate"] is None
        export = test_client.get(f"/api/v1/exams/{eid}/export", headers=_token(lecturer))
        assert export.status_code == 200
        wb = load_workbook(BytesIO(export.content))
        assert wb.sheetnames == ["Lượt làm", "Chưa làm", "Thống kê", "Câu hỏi"]
        assert wb["Lượt làm"].cell(2, 6).value == 9.5
        assert "Bài làm tự luận" not in str([list(s.values) for s in wb])
        assert test_client.post(f"/api/v1/exams/{eid}/close", headers=_token(lecturer)).status_code == 200
        after = test_client.get(f"/api/v1/attempts/{aid}/result", headers=_token(student))
        assert after.status_code == (403 if policy == "never" else 200)


def test_close_time_clamps_original_duration_and_never_revives(test_client, db_session):
    _, lecturer, student, eid, _, _ = setup_exam(test_client, db_session)
    with override_clock(OPEN):
        first = begin(test_client, student, eid)
        url = f"/api/v1/exams/{eid}/close-time"
        assert test_client.patch(url, headers=_token(lecturer), json={"close_at": "2026-10-20T08:20:00+07:00"}).status_code == 200
        assert test_client.get(f"/api/v1/attempts/{first['id']}", headers=_token(student)).json()["deadline_at"] == "2026-10-20T01:20:00Z"
        assert test_client.patch(url, headers=_token(lecturer), json={"close_at": "2026-10-20T12:00:00+07:00"}).status_code == 200
        assert test_client.get(f"/api/v1/attempts/{first['id']}", headers=_token(student)).json()["deadline_at"] == "2026-10-20T02:00:00Z"
    with override_clock(OPEN + timedelta(minutes=61)):
        assert test_client.patch(url, headers=_token(lecturer), json={"close_at": "2026-10-20T13:00:00+07:00"}).status_code == 200
        expired = test_client.get(f"/api/v1/attempts/{first['id']}", headers=_token(student)).json()
        assert expired["status"] == "auto_submitted"
        second = begin(test_client, student, eid)
        assert second["id"] != first["id"]
        assert test_client.post(f"/api/v1/exams/{eid}/close", headers=_token(lecturer)).status_code == 200
        assert test_client.get(f"/api/v1/attempts/{second['id']}", headers=_token(student)).json()["is_auto_submitted"] is True
        assert test_client.post(f"/api/v1/exams/{eid}/attempts", headers=_token(student)).status_code == 409


def test_events_idempotency_threshold_privacy_and_permissions(test_client, db_session):
    _, lecturer, student, eid, _, _ = setup_exam(test_client, db_session)
    _, _, outsider = _learning_data(db_session)
    with override_clock(OPEN):
        attempt = begin(test_client, student, eid)
        url = f"/api/v1/attempts/{attempt['id']}/events"
        event = {"event_id": str(uuid4()), "type": "copy"}
        assert test_client.post(url, headers=_token(outsider), json=event).status_code == 403
        assert test_client.post(url, headers=_token(lecturer), json=event).status_code == 403
        for extra in ({"meta": {"clipboard": "secret"}}, {"occurred_at": OPEN.isoformat()}):
            assert test_client.post(url, headers=_token(student), json={**event, **extra}).status_code == 422
        for _ in range(2):
            receipt = test_client.post(url, headers=_token(student), json=event)
            assert receipt.status_code == 200, receipt.text
            assert receipt.json()["violation_count"] == 1
        assert test_client.post(url, headers=_token(student), json={**event, "type": "paste"}).status_code == 409
        ignored = test_client.post(url, headers=_token(student), json={"event_id": str(uuid4()), "type": "fullscreen_exit"}).json()
        assert ignored["recorded"] is False
        reconnect = test_client.post(url, headers=_token(student), json={"event_id": str(uuid4()), "type": "reconnect"}).json()
        assert reconnect["violation_count"] == 1
        last = test_client.post(url, headers=_token(student), json={"event_id": str(uuid4()), "type": "copy"}).json()
        assert last["is_auto_submitted"] is True and last["violation_count"] == 2
        assert test_client.post(url, headers=_token(student), json={"event_id": str(uuid4()), "type": "copy"}).json()["recorded"] is False
        assert test_client.get(url, headers=_token(student)).status_code == 403
        log = test_client.get(url, headers=_token(lecturer)).json()
        assert log["total"] == 3 and sum(e["counted"] for e in log["items"]) == 2
        assert log["items"][0]["occurred_at"] == "2026-10-20T01:00:00Z"


def test_manager_endpoints_deny_foreign_class_and_student(test_client, db_session):
    _, lecturer, student, eid, questions, _ = setup_exam(test_client, db_session)
    _, foreign, _ = _learning_data(db_session)
    with override_clock(OPEN):
        attempt = begin(test_client, student, eid)
        for user in (student, foreign):
            for path in (f"exams/{eid}/stats", f"exams/{eid}/export", f"exams/{eid}/attempts", f"attempts/{attempt['id']}/review", f"attempts/{attempt['id']}/events"):
                assert test_client.get(f"/api/v1/{path}", headers=_token(user)).status_code == 403
            for action in ("close", "publish"):
                assert test_client.post(f"/api/v1/exams/{eid}/{action}", headers=_token(user)).status_code == 403
            assert test_client.patch(f"/api/v1/exams/{eid}/close-time", headers=_token(user), json={"close_at": "2026-10-20T11:00:00+07:00"}).status_code == 403
        # In-progress essays cannot be graded even by the correct teacher.
        assert test_client.post(f"/api/v1/attempts/{attempt['id']}/questions/{questions[-1]['id']}/grade", headers=_token(lecturer), json={"score": 1}).status_code == 409


@pytest.mark.parametrize("policy,expected", [("highest", "9.50"), ("last", "7.50")])
def test_multiple_attempts_pending_and_score_selection(test_client, db_session, policy, expected):
    _, lecturer, student, eid, questions, _ = setup_exam(test_client, db_session, score_policy=policy)
    with override_clock(OPEN):
        first = begin(test_client, student, eid)
        answer_and_submit(test_client, student, first, questions)
        qid = questions[-1]["id"]
        assert test_client.post(f"/api/v1/attempts/{first['id']}/questions/{qid}/grade", headers=_token(lecturer), json={"score": "2"}).status_code == 200
        second = begin(test_client, student, eid)
        answer_and_submit(test_client, student, second, questions)
        pending = test_client.get(f"/api/v1/exams/{eid}/results", headers=_token(student)).json()
        assert pending["score10"] is None
        assert test_client.get(f"/api/v1/exams/{eid}/stats", headers=_token(lecturer)).json()["graded_students"] == 0
        assert test_client.post(f"/api/v1/attempts/{second['id']}/questions/{qid}/grade", headers=_token(lecturer), json={"score": "0"}).status_code == 200
        final = test_client.get(f"/api/v1/exams/{eid}/results", headers=_token(student)).json()
        assert final["score10"] == expected
        assert test_client.get(f"/api/v1/exams/{eid}/stats", headers=_token(lecturer)).json()["average"] == expected


def test_closed_class_is_read_only_for_exam_mutations(test_client, db_session):
    cls, lecturer, student, eid, questions, _ = setup_exam(test_client, db_session)
    with override_clock(OPEN):
        attempt = begin(test_client, student, eid)
        db_session.refresh(cls)
        cls.status = ClassStatus.closed
        db_session.commit()
        base = f"/api/v1/attempts/{attempt['id']}"
        for response in [
            test_client.post(f"/api/v1/exams/{eid}/attempts", headers=_token(student)),
            test_client.post(f"{base}/submit", headers=_token(student)),
            test_client.put(f"{base}/answers/{questions[0]['id']}", headers=_token(student), json={}),
            test_client.post(f"{base}/events", headers=_token(student), json={"event_id": str(uuid4()), "type": "copy"}),
            test_client.post(f"/api/v1/exams/{eid}/close", headers=_token(lecturer)),
        ]:
            assert response.status_code == 409, response.text
        assert test_client.get(base, headers=_token(student)).status_code == 200
        assert test_client.get(f"{base}/review", headers=_token(lecturer)).status_code == 200


def test_concurrent_event_retries_count_once_and_threshold_is_atomic(test_client, db_session, test_engine):
    _, lecturer, student, eid, _, _ = setup_exam(test_client, db_session, max_violations=3)
    with override_clock(OPEN):
        aid = begin(test_client, student, eid)["id"]
    user_id = student.id
    def batch(event_ids):
        barrier = Barrier(len(event_ids))
        def worker(event_id):
            with Session(test_engine) as db, override_clock(OPEN):
                user = db.get(User, user_id)
                barrier.wait(timeout=10)
                return record_event(db, user, aid, ExamEventIn(event_id=event_id, type="copy"))
        with ThreadPoolExecutor(max_workers=len(event_ids)) as pool:
            return list(pool.map(worker, event_ids))
    same = str(uuid4())
    assert all(r["violation_count"] == 1 for r in batch([same] * 4))
    receipts = batch([str(uuid4()) for _ in range(3)])
    assert max(r["violation_count"] for r in receipts) == 3
    with override_clock(OPEN):
        attempt = test_client.get(f"/api/v1/attempts/{aid}", headers=_token(student)).json()
        assert attempt["violation_count"] == 3 and attempt["is_auto_submitted"] is True
        assert test_client.get(f"/api/v1/attempts/{aid}/events", headers=_token(lecturer)).json()["total"] == 3
