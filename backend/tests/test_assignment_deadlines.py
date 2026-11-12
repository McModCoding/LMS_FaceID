"""F02: timezone-aware API deadlines round-trip through MySQL as UTC."""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import text

from app.core.config import settings
from app.models.learning import Submission
from app.utils.clock import VN_TZ, override_clock
from tests.test_m4_m5 import _learning_data, _token

DEADLINE = datetime(2026, 10, 30, 10, tzinfo=UTC)


def _create(client, cls, lecturer, due_at, allow_late=False):
    return client.post(f"/api/v1/classes/{cls.id}/assignments", headers=_token(lecturer), json={
        "title": "F02 deadline", "due_at": due_at, "status": "published",
        "allow_late": allow_late,
    })


def _instant(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


@pytest.mark.parametrize("due_at", [
    "2026-10-30T10:00:00Z", "2026-10-30T17:00:00+07:00", "2026-10-30T05:00:00-05:00",
])
@pytest.mark.parametrize("delta", [-1, 0, 1])
def test_deadline_round_trip_and_text_submission_boundaries(test_client, db_session, due_at, delta):
    cls, lecturer, student = _learning_data(db_session)
    created = _create(test_client, cls, lecturer, due_at)
    assert created.status_code == 200, created.text
    assignment_id = created.json()["id"]
    assert _instant(created.json()["due_at"]) == DEADLINE
    assert _instant(created.json()["due_at"]).utcoffset() == timedelta(0)
    # Raw SQL confirms storage independently of response formatting and ORM identity maps.
    stored = db_session.execute(text("SELECT due_at FROM assignments WHERE id=:id"), {"id": assignment_id}).scalar_one()
    assert stored == DEADLINE.replace(tzinfo=None)
    listing = test_client.get(f"/api/v1/classes/{cls.id}/assignments", headers=_token(student))
    assert _instant(listing.json()["items"][0]["due_at"]) == DEADLINE
    with override_clock((DEADLINE + timedelta(seconds=delta)).astimezone(VN_TZ)):
        response = test_client.post(f"/api/v1/assignments/{assignment_id}/submissions",
            headers=_token(student), json={
                "text": "Bài nộp", "submitted_at": "2026-10-30T00:00:00Z", "is_late": False,
            })
    assert response.status_code == (409 if delta > 0 else 200), response.text
    if delta > 0:
        assert response.json()["detail"]["code"] == "ASSIGNMENT_CLOSED"
        assert db_session.query(Submission).filter_by(assignment_id=assignment_id).count() == 0
    else:
        assert response.json()["is_late"] is False


@pytest.mark.parametrize("delta", [-1, 0, 1])
def test_file_submission_uses_same_deadline(test_client, db_session, monkeypatch, tmp_path, delta):
    cls, lecturer, student = _learning_data(db_session)
    monkeypatch.setattr(settings, "UPLOAD_STORAGE_DIR", str(tmp_path))
    assignment_id = _create(test_client, cls, lecturer, "2026-10-30T17:00:00+07:00").json()["id"]
    with override_clock((DEADLINE + timedelta(seconds=delta)).astimezone(VN_TZ)):
        response = test_client.post(f"/api/v1/assignments/{assignment_id}/submissions/file",
            headers=_token(student), files={"file": ("answer.txt", b"answer", "text/plain")})
    assert response.status_code == (409 if delta > 0 else 200), response.text
    if delta > 0:
        assert response.json()["detail"]["code"] == "ASSIGNMENT_CLOSED"
        assert not list(tmp_path.rglob("*.txt"))
    else:
        assert response.json()["is_late"] is False


def test_late_policy_and_rejected_resubmission_preserve_answer(test_client, db_session):
    cls, lecturer, student = _learning_data(db_session)
    assignment_id = _create(test_client, cls, lecturer, DEADLINE.isoformat()).json()["id"]
    url = f"/api/v1/assignments/{assignment_id}/submissions"
    with override_clock(DEADLINE.astimezone(VN_TZ)):
        first = test_client.post(url, headers=_token(student), json={"text": "Original"})
    with override_clock((DEADLINE + timedelta(microseconds=1)).astimezone(VN_TZ)):
        rejected = test_client.post(url, headers=_token(student), json={"text": "Too late"})
    assert rejected.status_code == 409
    db_session.expire_all()
    assert db_session.get(Submission, first.json()["id"]).text == "Original"
    edited = test_client.patch(f"/api/v1/assignments/{assignment_id}", headers=_token(lecturer), json={
        "title": "Late permitted", "due_at": "2026-10-30T17:00:00+07:00",
        "allow_late": True, "status": "published",
    })
    assert edited.status_code == 200
    with override_clock((DEADLINE + timedelta(seconds=1)).astimezone(VN_TZ)):
        late = test_client.post(url, headers=_token(student), json={"text": "Late permitted"})
    assert late.status_code == 200
    assert late.json()["is_late"] is True
    assert late.json()["id"] == first.json()["id"]


def test_update_deadline_crosses_date_boundary(test_client, db_session):
    cls, lecturer, student = _learning_data(db_session)
    assignment_id = _create(test_client, cls, lecturer, DEADLINE.isoformat()).json()["id"]
    response = test_client.patch(f"/api/v1/assignments/{assignment_id}", headers=_token(lecturer), json={
        "title": "Next day VN", "due_at": "2026-10-31T00:30:00+07:00", "status": "published",
    })
    assert response.status_code == 200
    assert _instant(response.json()["due_at"]) == datetime(2026, 10, 30, 17, 30, tzinfo=UTC)
    with override_clock(datetime(2026, 10, 31, 0, 29, tzinfo=VN_TZ)):
        submitted = test_client.post(f"/api/v1/assignments/{assignment_id}/submissions",
            headers=_token(student), json={"text": "Next day"})
    assert submitted.status_code == 200
    assert submitted.json()["is_late"] is False


@pytest.mark.parametrize("invalid", ["2026-10-30T17:00:00", "invalid", None])
def test_reject_deadline_without_timezone_or_invalid_value(test_client, db_session, invalid):
    cls, lecturer, _ = _learning_data(db_session)
    response = _create(test_client, cls, lecturer, invalid)
    assert response.status_code == 422
    listing = test_client.get(f"/api/v1/classes/{cls.id}/assignments", headers=_token(lecturer))
    assert listing.json()["total"] == 0

def test_assignment_list_status_and_pending_counts(test_client, db_session):
    cls, lecturer, student = _learning_data(db_session)
    assignment_id = _create(test_client, cls, lecturer, DEADLINE.isoformat()).json()["id"]
    url = f"/api/v1/classes/{cls.id}/assignments"
    with override_clock(DEADLINE.astimezone(VN_TZ)):
        assert test_client.get(url, headers=_token(student)).json()["items"][0]["availability"] == "open"
    with override_clock((DEADLINE + timedelta(seconds=1)).astimezone(VN_TZ)):
        assert test_client.get(url, headers=_token(student)).json()["items"][0]["availability"] == "closed"
    with override_clock(DEADLINE.astimezone(VN_TZ)):
        assert test_client.post(f"/api/v1/assignments/{assignment_id}/submissions", headers=_token(student), json={"text": "Bài nộp"}).status_code == 200
        assert test_client.get(url, headers=_token(student)).json()["items"][0]["availability"] == "submitted"
        assert test_client.get(url, headers=_token(lecturer)).json()["items"][0]["pending_count"] == 1
        assert test_client.get(url, headers=_token(student), params={"view": "submitted"}).json()["total"] == 1
        assert test_client.get(url, headers=_token(student), params={"view": "todo"}).json()["total"] == 0
        assert test_client.get(url, headers=_token(lecturer), params={"view": "pending"}).json()["total"] == 1
        assert test_client.get(url, headers=_token(student), params={"view": "pending"}).status_code == 422
    with override_clock((DEADLINE + timedelta(seconds=1)).astimezone(VN_TZ)):
        row = test_client.get(url, headers=_token(student)).json()["items"][0]
        assert row["availability"] == "submitted"
        assert row["can_submit"] is False


def test_closed_class_assignments_are_history_not_todo(test_client, db_session):
    from app.models.class_ import ClassStatus
    cls, lecturer, student = _learning_data(db_session)
    _create(test_client, cls, lecturer, (DEADLINE + timedelta(days=1)).isoformat(), allow_late=True)
    cls.status = ClassStatus.closed
    db_session.commit()
    url = f"/api/v1/classes/{cls.id}/assignments"
    with override_clock(DEADLINE.astimezone(VN_TZ)):
        assert test_client.get(url, headers=_token(student), params={"view": "todo"}).json()["total"] == 0
        history = test_client.get(url, headers=_token(student), params={"view": "finished"}).json()
        assert history["total"] == 1
        assert history["items"][0]["availability"] == "closed"
        assert history["items"][0]["can_submit"] is False
        assert test_client.get(url, headers=_token(lecturer), params={"view": "finished"}).json()["total"] == 1
