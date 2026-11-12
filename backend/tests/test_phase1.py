"""Phase 1 regressions: class-scoped leave workflows and basic materials."""

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from fastapi import HTTPException
from sqlalchemy.orm import sessionmaker

from app.core.security import create_access_token
from app.models.attendance import LeaveRequest, LeaveRequestStatus
from app.models.class_ import Class, ClassStatus, ClassStudent, ClassStudentStatus
from app.models.session import Session as SessionModel
from app.models.session import SessionStatus
from app.schemas.leave_request import LeaveRequestCreate
from app.services.leave_request_service import create_leave_request
from tests import test_leave_request as leave_fixtures

lr_data = leave_fixtures.lr_data


def headers(user):
    return {"Authorization": "Bearer " + create_access_token({
        "sub": str(user.id), "role": user.role.value, "token_version": user.token_version,
    })}


def test_leave_filters_and_review_notifications(test_client, db_session, lr_data):
    d = lr_data
    cls = d["cls"]
    other = Class(code=cls.code + "_2", subject_id=cls.subject_id, semester_id=cls.semester_id,
                  lecturer_id=cls.lecturer_id, status=ClassStatus.active, max_students=30)
    db_session.add(other)
    db_session.flush()
    db_session.add(ClassStudent(class_id=other.id, student_id=d["stu"].id, status=ClassStudentStatus.enrolled))
    session = SessionModel(class_id=other.id, session_no=1, date=d["sess_future"].date,
                           start_time=d["sess_future"].start_time, end_time=d["sess_future"].end_time,
                           room="B2", status=SessionStatus.scheduled)
    db_session.add(session)
    db_session.commit()
    for sess in [d["sess_future"], session]:
        result = test_client.post(f"/api/v1/sessions/{sess.id}/leave-requests", headers=headers(d["u_stu"]),
                                  json={"session_id": sess.id, "reason": "  Có việc gia đình  "})
        assert result.status_code == 200
        assert result.json()["reason"] == "Có việc gia đình"
    path = "/api/v1/leave-requests"
    result = test_client.get(path, headers=headers(d["u_lec"]), params={"class_id": cls.id})
    assert result.status_code == 200
    assert result.json()["total"] == 1
    assert result.json()["items"][0]["class_id"] == cls.id
    request_id = result.json()["items"][0]["id"]
    result = test_client.post(f"{path}/{request_id}/review", headers=headers(d["u_lec"]), json={"decision": "approve", "review_note": "Đồng ý"})
    assert result.status_code == 200
    assert result.json()["reviewer_name"] == d["u_lec"].username
    assert result.json()["reviewed_at"].endswith("+07:00")
    assert result.json()["created_at"].endswith(("Z", "+00:00"))
    result = test_client.get("/api/v1/me/leave-requests", headers=headers(d["u_stu"]), params={"class_id": cls.id, "status": "approved"})
    assert result.json()["total"] == 1
    assert result.json()["items"][0]["review_note"] == "Đồng ý"
    notices = test_client.get("/api/v1/notifications", headers=headers(d["u_stu"])).json()
    assert any(item["type"] == "leave_request_reviewed" for item in notices["items"])
    assert test_client.get("/api/v1/me/leave-requests", headers=headers(d["u_stu2"]), params={"class_id": cls.id}).status_code == 403


def test_blank_leave_reason_rejected(test_client, lr_data):
    d = lr_data
    result = test_client.post(f"/api/v1/sessions/{d['sess_future'].id}/leave-requests",
                              headers=headers(d["u_stu"]), json={"session_id": d["sess_future"].id, "reason": "   "})
    assert result.status_code == 422


def test_concurrent_leave_only_one_pending(test_engine, db_session, lr_data):
    if test_engine.dialect.name != "mysql":
        pytest.skip("Row locking requires MySQL")
    student_id, session_id = lr_data["stu"].id, lr_data["sess_future"].id
    factory = sessionmaker(bind=test_engine)
    barrier = Barrier(2)

    def send():
        with factory() as session:
            barrier.wait(timeout=10)
            try:
                create_leave_request(session, student_id, LeaveRequestCreate(session_id=session_id, reason="Đơn đồng thời"))
                return "created"
            except HTTPException as exc:
                session.rollback()
                return exc.detail["code"]

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(lambda _: send(), range(2)))
    assert sorted(results) == ["DUPLICATE_PENDING_REQUEST", "created"]
    assert db_session.query(LeaveRequest).filter_by(student_id=student_id, session_id=session_id, status=LeaveRequestStatus.pending).count() == 1


def test_material_file_link_permissions_and_lifecycle(test_client, db_session, lr_data):
    d = lr_data
    path = f"/api/v1/classes/{d['cls'].id}/materials"
    lecturer, student, outsider = headers(d["u_lec"]), headers(d["u_stu"]), headers(d["u_stu2"])
    assert test_client.get(path, headers=outsider).status_code == 403
    assert test_client.post(path, headers=student, data={"title": "Học liệu", "url": "https://example.org"}).status_code == 403
    result = test_client.post(path, headers=lecturer, data={"title": " Link ", "url": "https://example.org/lesson", "description": "Mô tả"})
    assert result.status_code == 201
    link_id = result.json()["id"]
    assert result.json()["title"] == "Link"
    assert "file_path" not in result.json()
    result = test_client.post(path, headers=lecturer, data={"title": "Tài liệu"}, files={"file": ("demo.txt", b"Lesson from a real upload", "text/plain")})
    assert result.status_code == 201
    file_id = result.json()["id"]
    download = f"/api/v1/materials/{file_id}/file"
    assert test_client.get(download, headers=student).content == b"Lesson from a real upload"
    assert test_client.get(download, headers=outsider).status_code == 403
    assert test_client.get(path, headers=student, params={"page_size": 1}).json()["total"] == 2
    result = test_client.patch(f"/api/v1/materials/{link_id}", headers=lecturer, json={"title": "Đã sửa", "description": "Nội dung mới"})
    assert result.status_code == 200 and result.json()["title"] == "Đã sửa"
    assert test_client.delete(f"/api/v1/materials/{file_id}", headers=student).status_code == 403
    assert test_client.delete(f"/api/v1/materials/{file_id}", headers=lecturer).status_code == 204
    assert test_client.get(download, headers=student).status_code == 404
    d["cls"].status = ClassStatus.closed
    db_session.commit()
    assert test_client.get(path, headers=student).status_code == 200
    assert test_client.post(path, headers=lecturer, data={"title": "Mới", "url": "https://example.org"}).status_code == 409
    assert test_client.patch(f"/api/v1/materials/{link_id}", headers=lecturer, json={"title": "Sửa"}).status_code == 409
    assert test_client.delete(f"/api/v1/materials/{link_id}", headers=lecturer).status_code == 409


@pytest.mark.parametrize("url", ["http://example.org", "javascript:alert(1)", "https://user:pass@example.org", "https://", "https://example.org:bad"])
def test_material_rejects_unsafe_links(test_client, lr_data, url):
    result = test_client.post(f"/api/v1/classes/{lr_data['cls'].id}/materials", headers=headers(lr_data["u_lec"]), data={"title": "Không hợp lệ", "url": url})
    assert result.status_code == 422
    assert result.json()["detail"]["code"] == "INVALID_MATERIAL_URL"


def test_material_rejects_bad_upload_and_source(test_client, lr_data, monkeypatch):
    from app.core.config import settings

    path = f"/api/v1/classes/{lr_data['cls'].id}/materials"
    auth = headers(lr_data["u_lec"])
    assert test_client.post(path, headers=auth, data={"title": "Không có nguồn"}).status_code == 422
    assert test_client.post(path, headers=auth, data={"title": "Sai tệp"}, files={"file": ("fake.pdf", b"Not PDF", "application/pdf")}).status_code == 422
    assert test_client.post(path, headers=auth, data={"title": "Hai nguồn", "url": "https://example.org"}, files={"file": ("x.txt", b"text", "text/plain")}).status_code == 422
    monkeypatch.setattr(settings, "MAX_UPLOAD_SIZE_MB", 1)
    assert test_client.post(path, headers=auth, data={"title": "Quá lớn"}, files={"file": ("big.txt", b"x" * (1024 * 1024 + 1), "text/plain")}).status_code == 413
