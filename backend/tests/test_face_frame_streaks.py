"""F04: count distinct, consecutive valid frames, never ambiguous/replayed hits."""

from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, time
from threading import Barrier
from uuid import uuid4

import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.core.config import Settings, settings
from app.face.base import FaceBox, MatchResult
from app.models.attendance import (
    AttendanceHistory,
    AttendanceRecord,
    AttendanceSource,
    AttendanceStatus,
)
from app.models.class_ import ClassStudent, ClassStudentStatus
from app.models.learning import (
    FaceConsent,
    FaceTemplate,
    FaceTemplateStatus,
    RecognitionFrame,
    RecognitionLog,
)
from app.models.session import Session as SessionModel
from app.models.session import SessionStatus
from app.models.student import Student
from app.services import attendance_service, face_service
from app.utils.clock import VN_TZ, override_clock
from tests.test_m4_m5 import _learning_data, _second_student, _token


class StubEngine:
    name = "f04-test-only"
    version = "1"
    is_ready = True

    def __init__(self):
        self.results = []
        self.calls = 0

    def identify(self, frame, candidates):
        self.calls += 1
        return self.results


def match(student_id, status="matched", score=0.9, margin=0.2):
    return MatchResult(FaceBox(0.1, 0.1, 0.3, 0.4, 0.99), student_id, status, score, margin)


@pytest.fixture
def scene(db_session, monkeypatch, tmp_path):
    cls, lecturer, user = _learning_data(db_session)
    student = db_session.query(Student).filter_by(user_id=user.id).one()
    other, _ = _second_student(db_session, cls)
    for member in (student, other):
        db_session.add(FaceConsent(student_id=member.id, text_version="f04-test", consented_at=datetime(2026, 10, 18, 8)))
        db_session.add(FaceTemplate(student_id=member.id, image_path=str(tmp_path / str(member.id) / "test.jpg"),
                                   embedding=b"f04-test-only", status=FaceTemplateStatus.active))
    session = SessionModel(class_id=cls.id, session_no=1, date=date(2026, 10, 18),
        start_time=time(8), end_time=time(10), room="F04", status=SessionStatus.open)
    db_session.add(session)
    db_session.flush()
    attendance_service.ensure_records(db_session, session)
    db_session.commit()
    engine = StubEngine()
    monkeypatch.setattr(face_service, "get_engine", lambda: engine)
    monkeypatch.setattr(settings, "FACE_MIN_HITS", 3)
    monkeypatch.setattr(settings, "FACE_MATCH_THRESHOLD", 0.7)
    monkeypatch.setattr(settings, "FACE_MARGIN_THRESHOLD", 0.1)
    with override_clock(datetime(2026, 10, 18, 8, 5, tzinfo=VN_TZ)):
        yield {"session": session, "student": student, "other": other,
               "lecturer": lecturer, "user": user, "engine": engine}


def send(db, scene, results, frame_id=None, content=b"frame"):
    scene["engine"].results = results
    return face_service.recognize(db, scene["session"].id, content, frame_id or str(uuid4()))


def record(db, scene, student=None):
    db.expire_all()
    return db.query(AttendanceRecord).filter_by(
        session_id=scene["session"].id, student_id=(student or scene["student"]).id,
    ).one()


def test_three_distinct_valid_frames_mark_present_once(db_session, scene):
    for hits in range(1, 4):
        result = send(db_session, scene, [match(scene["student"].id)])
        row = record(db_session, scene)
        assert row.hit_count == hits
        assert row.status == (AttendanceStatus.present if hits == 3 else AttendanceStatus.absent)
        assert bool(result["attendance_changes"]) == (hits == 3)
    row = record(db_session, scene)
    assert row.source == AttendanceSource.face
    assert row.first_seen_at is not None
    assert db_session.query(AttendanceHistory).filter_by(record_id=row.id).count() == 1
    send(db_session, scene, [])
    assert record(db_session, scene).status == AttendanceStatus.present
    assert record(db_session, scene).hit_count == 0


@pytest.mark.parametrize("interruption", ["no_face", "unknown", "ambiguous", "low_quality", "other_student", "foreign_id"])
def test_interruption_resets_streak_without_marking_attendance(db_session, scene, interruption):
    student_id = scene["student"].id
    send(db_session, scene, [match(student_id)])
    send(db_session, scene, [match(student_id)])
    frames = {
        "no_face": [], "unknown": [match(None, "unknown")],
        "ambiguous": [match(student_id, "ambiguous")],
        "low_quality": [match(student_id, "low_quality")],
        "other_student": [match(scene["other"].id)],
        "foreign_id": [match(999999999)],
    }
    send(db_session, scene, frames[interruption])
    assert record(db_session, scene).hit_count == 0
    assert record(db_session, scene).status == AttendanceStatus.absent
    send(db_session, scene, [match(student_id)])
    assert record(db_session, scene).hit_count == 1
    assert record(db_session, scene).status == AttendanceStatus.absent


@pytest.mark.parametrize("score,margin", [
    (0.69, 0.2), (0.9, 0.09), (None, 0.2), (0.9, None),
    (float("nan"), 0.2), (0.9, float("nan")), (float("inf"), 0.2), (0.9, float("inf")),
])
def test_invalid_confidence_breaks_streak_and_never_writes_nonfinite_json(db_session, scene, score, margin):
    student_id = scene["student"].id
    send(db_session, scene, [match(student_id)])
    response = send(db_session, scene, [match(student_id, score=score, margin=margin)])
    assert response["faces"][0]["status"] != "matched"
    assert record(db_session, scene).hit_count == 0
    assert record(db_session, scene).status == AttendanceStatus.absent


def test_duplicate_identity_boxes_are_ambiguous_not_multiple_hits(db_session, scene):
    student_id = scene["student"].id
    send(db_session, scene, [match(student_id)])
    response = send(db_session, scene, [match(student_id), match(student_id), match(student_id)])
    assert all(face["status"] == "ambiguous" for face in response["faces"])
    assert not response["attendance_changes"]
    assert record(db_session, scene).hit_count == 0


def test_multiple_students_each_get_one_hit_per_frame(db_session, scene):
    for _ in range(3):
        send(db_session, scene, [match(scene["student"].id), match(scene["other"].id)])
    assert record(db_session, scene).status == AttendanceStatus.present
    assert record(db_session, scene, scene["other"]).status == AttendanceStatus.present


def test_retry_frame_is_idempotent_and_reuse_with_different_content_is_rejected(db_session, scene):
    frame_id = str(uuid4())
    first = send(db_session, scene, [match(scene["student"].id)], frame_id)
    for _ in range(3):
        assert send(db_session, scene, [], frame_id) == first
    assert record(db_session, scene).hit_count == 1
    assert scene["engine"].calls == 1
    assert db_session.query(RecognitionLog).filter_by(session_id=scene["session"].id).count() == 1
    with pytest.raises(HTTPException) as error:
        send(db_session, scene, [], frame_id, b"different")
    assert error.value.detail["code"] == "FRAME_ID_REUSED"
    db_session.rollback()
    assert record(db_session, scene).hit_count == 1


@pytest.mark.parametrize("minute,status", [(10, "present"), (11, "late"), (30, "late"), (31, "absent")])
def test_threshold_boundaries_and_attendance_time_rules(db_session, scene, minute, status):
    with override_clock(datetime(2026, 10, 18, 8, minute, tzinfo=VN_TZ)):
        for _ in range(3):
            send(db_session, scene, [match(scene["student"].id, score=0.7, margin=0.1)])
    assert record(db_session, scene).status.value == status


@pytest.mark.parametrize("status", [AttendanceStatus.present, AttendanceStatus.late, AttendanceStatus.excused])
def test_reset_never_downgrades_existing_attendance(db_session, scene, status):
    row = record(db_session, scene)
    row.status = status
    row.source = AttendanceSource.manual
    row.hit_count = 2
    db_session.commit()
    send(db_session, scene, [])
    row = record(db_session, scene)
    assert row.status == status
    assert row.source == AttendanceSource.manual
    assert row.hit_count == 0


def test_missing_frame_id_and_closed_session_do_not_mutate(db_session, scene):
    with pytest.raises(HTTPException) as error:
        face_service.recognize(db_session, scene["session"].id, b"frame")
    assert error.value.detail["code"] == "FRAME_ID_REQUIRED"
    scene["session"].status = SessionStatus.closed
    db_session.commit()
    with pytest.raises(HTTPException) as error:
        send(db_session, scene, [match(scene["student"].id)])
    assert error.value.detail["code"] == "SESSION_NOT_OPEN"
    db_session.rollback()
    assert record(db_session, scene).hit_count == 0


def test_frame_failure_rolls_back_and_can_retry_same_id(db_session, scene, monkeypatch):
    frame_id = str(uuid4())
    original = attendance_service.reset_missing_face_hits
    def fail(*args):
        raise RuntimeError("test transaction failure")
    monkeypatch.setattr(attendance_service, "reset_missing_face_hits", fail)
    with pytest.raises(RuntimeError):
        send(db_session, scene, [match(scene["student"].id)], frame_id)
    db_session.rollback()
    assert record(db_session, scene).hit_count == 0
    assert db_session.query(RecognitionFrame).filter_by(session_id=scene["session"].id).count() == 0
    monkeypatch.setattr(attendance_service, "reset_missing_face_hits", original)
    send(db_session, scene, [match(scene["student"].id)], frame_id)
    assert record(db_session, scene).hit_count == 1


def test_api_checks_role_frame_id_and_retry(test_client, db_session, scene):
    url = f"/api/v1/sessions/{scene['session'].id}/recognize"
    files = {"frame": ("frame.jpg", b"\xff\xd8\xfftest", "image/jpeg")}
    assert test_client.post(url, files=files, headers=_token(scene["user"])).status_code == 403
    assert test_client.post(url, files=files, headers=_token(scene["lecturer"])).status_code == 422
    assert test_client.post(url, files=files, data={"frame_id": "invalid"}, headers=_token(scene["lecturer"])).status_code == 422
    frame_id = str(uuid4())
    scene["engine"].results = [match(scene["student"].id)]
    for _ in range(3):
        response = test_client.post(url, files=files, data={"frame_id": frame_id}, headers=_token(scene["lecturer"]))
        assert response.status_code == 200, response.text
    assert record(db_session, scene).hit_count == 1


@pytest.mark.parametrize("same_id", [True, False])
def test_simultaneous_frames_are_serialized_on_mysql(db_session, test_engine, scene, same_id):
    assert test_engine.dialect.name == "mysql", "F04 concurrency verification requires MySQL"
    session_id = scene["session"].id
    scene["engine"].results = [match(scene["student"].id)]
    ids = [str(uuid4()), str(uuid4())]
    if same_id:
        ids[1] = ids[0]
    barrier = Barrier(2, timeout=20)
    def recognize(frame_id):
        with Session(test_engine) as db:
            barrier.wait()
            return face_service.recognize(db, session_id, b"frame", frame_id)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(recognize, ids))
    assert all(response["ready"] for response in results)
    assert record(db_session, scene).hit_count == (1 if same_id else 2)
    assert scene["engine"].calls == (1 if same_id else 2)


@pytest.mark.parametrize("invalid", [
    {"FACE_MIN_HITS": 0}, {"FACE_MATCH_THRESHOLD": float("nan")},
    {"FACE_MARGIN_THRESHOLD": float("inf")},
])
def test_invalid_streak_configuration_is_rejected(invalid):
    with pytest.raises(ValidationError):
        Settings(_env_file=None, **invalid)


def test_withdrawn_student_cannot_continue_streak(db_session, scene):
    student_id = scene["student"].id
    send(db_session, scene, [match(student_id)])
    enrollment = db_session.query(ClassStudent).filter_by(
        class_id=scene["session"].class_id, student_id=student_id,
    ).one()
    enrollment.status = ClassStudentStatus.dropped
    db_session.commit()
    result = send(db_session, scene, [match(student_id)])
    assert result["faces"][0]["status"] == "unknown"
    assert result["faces"][0]["student_id"] is None
    assert record(db_session, scene).hit_count == 0
    assert record(db_session, scene).status == AttendanceStatus.absent


@pytest.mark.parametrize("score,margin", [(float("nan"), 0.2), (0.9, float("inf"))])
def test_attendance_layer_rejects_nonfinite_match(db_session, scene, score, margin):
    _, code = attendance_service.apply_face_match(
        db_session, scene["session"], scene["student"].id, score, margin,
    )
    assert code == "below_threshold"
    db_session.commit()
    assert record(db_session, scene).hit_count == 0
