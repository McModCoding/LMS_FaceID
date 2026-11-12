import json
from datetime import datetime
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import event

from app.models.audit import AuditLog
from app.models.class_ import ClassStudent, ClassStudentStatus
from app.models.grade import GradeComponent
from app.models.student import Student, StudentStatus
from app.models.user import User, UserRole
from app.services.grade_service import gradebook
from tests.test_m4_m5 import _admin, _learning_data, _token


def test_audit_vietnam_day_boundary_order_redaction_and_acl(test_client, db_session):
    _, lecturer, student = _learning_data(db_session)
    admin = _admin(db_session, uuid4().hex[:8])
    action = "M8_BOUNDARY_" + uuid4().hex[:8]
    dates = [datetime(2026, 11, 4, 16, 59, 59), datetime(2026, 11, 4, 17),
             datetime(2026, 11, 5, 16, 59, 59), datetime(2026, 11, 5, 17)]
    for index, timestamp in enumerate(dates):
        detail = {"password": "private-test-value", "nested": [{"api-key": "private-test-value", "score": 0}]}
        db_session.add(AuditLog(user_id=admin.id, action=action, entity="users", created_at=timestamp,
            detail=json.dumps(detail) if index == 2 else detail))
    db_session.commit()
    params = {"action": action, "date_from": "2026-11-05", "date_to": "2026-11-05"}
    for user in (lecturer, student):
        assert test_client.get("/api/v1/audit-logs", headers=_token(user), params=params).status_code == 403
    response = test_client.get("/api/v1/audit-logs", headers=_token(admin), params=params)
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["total"] == 2
    assert [item["created_at"] for item in data["items"]] == ["2026-11-05T16:59:59Z", "2026-11-04T17:00:00Z"]
    assert "private-test-value" not in response.text and "[REDACTED]" in response.text
    assert data["items"][0]["detail"]["nested"][0]["score"] == 0


@pytest.mark.parametrize("params", [
    {"date_from": "bad-date"}, {"date_from": "2026-11-05T10:00:00"},
    {"date_from": "2026-11-06", "date_to": "2026-11-05"},
])
def test_audit_invalid_dates_have_real_error(test_client, admin_headers, params):
    response = test_client.get("/api/v1/audit-logs", headers=admin_headers, params=params)
    assert response.status_code == 422 and response.json()["detail"]["message"]


def test_system_info_is_admin_only_and_safe_projection(test_client, db_session):
    _, lecturer, student = _learning_data(db_session)
    admin = _admin(db_session, uuid4().hex[:8])
    url = "/api/v1/admin/system-info"
    assert test_client.get(url).status_code == 401
    for user in (lecturer, student):
        assert test_client.get(url, headers=_token(user)).status_code == 403
    response = test_client.get(url, headers=_token(admin))
    assert response.status_code == 200
    data = response.json()
    assert data["timezone"] == "Asia/Ho_Chi_Minh" and data["face_ready"] is False
    assert not any(key in data for key in ("SECRET_KEY", "DB_PASSWORD", "DATABASE_URL", "embedding", "image_path"))
    assert test_client.patch(url, headers=_token(admin), json={"max_upload_mb": 50}).status_code == 405


def test_gradebook_batch_queries_do_not_grow_per_student(db_session, test_engine):
    cls, lecturer, _ = _learning_data(db_session)
    db_session.add(GradeComponent(class_id=cls.id, name="Nhập tay", type="manual", weight=100))
    db_session.commit()
    def measure():
        statements = []
        def capture(*args):
            statements.append(1)
        event.listen(test_engine, "before_cursor_execute", capture)
        try:
            return gradebook(db_session, lecturer, cls.id, page_size=100), len(statements)
        finally:
            event.remove(test_engine, "before_cursor_execute", capture)
    first, initial_count = measure()
    for _i in range(59):
        uid = uuid4().hex[:10]
        user = User(username="m8" + uid, email=uid + "@test.local", password_hash="not-a-login-hash", role=UserRole.student, is_active=True, is_deleted=False)
        db_session.add(user)
        db_session.flush()
        student = Student(user_id=user.id, student_code="M8" + uid, full_name="SV kiểm thử truy vấn", status=StudentStatus.studying, is_deleted=False)
        db_session.add(student)
        db_session.flush()
        db_session.add(ClassStudent(class_id=cls.id, student_id=student.id, status=ClassStudentStatus.enrolled))
    db_session.commit()
    final, final_count = measure()
    assert first["total"] == 1 and final["total"] == 60
    assert final_count <= initial_count + 1
    assert all(row["total_score"] == Decimal("0.0") for row in final["items"])
