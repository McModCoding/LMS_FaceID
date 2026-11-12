"""
test_sessions.py
Kiểm tra sửa buổi, hủy buổi, thêm buổi bù và timetable.
"""
import uuid
from datetime import date, time

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import create_access_token, get_password_hash
from app.models.class_ import Class, ClassStatus, ClassStudent, ClassStudentStatus
from app.models.lecturer import Lecturer, LecturerType
from app.models.semester import Semester
from app.models.session import Session as SessionModel
from app.models.session import SessionStatus
from app.models.student import Student, StudentStatus
from app.models.subject import Subject
from app.models.user import User, UserRole


def _tok(user: User) -> str:
    return create_access_token({"sub": str(user.id), "role": user.role.value, "token_version": user.token_version})


def _uid() -> str:
    return uuid.uuid4().hex[:8]


@pytest.fixture
def sess_data(db_session: Session):
    uid = _uid()
    sem = Semester(name=f"HK_SESS_{uid}", start_date=date(2026, 9, 1), end_date=date(2026, 12, 31))
    db_session.add(sem)
    sub = Subject(code=f"SESS_{uid}", name="Môn Buổi Học", credits=3)
    db_session.add(sub)

    u_admin = User(
        username=f"admin_sess_{uid}", email=f"admin_sess_{uid}@t.com",
        password_hash=get_password_hash("A"), role=UserRole.admin,
        is_active=True, must_change_password=False, is_deleted=False, token_version=1,
    )
    db_session.add(u_admin)
    u_lec = User(
        username=f"lec_sess_{uid}", email=f"lec_sess_{uid}@t.com",
        password_hash=get_password_hash("A"), role=UserRole.lecturer,
        is_active=True, must_change_password=False, is_deleted=False, token_version=1,
    )
    db_session.add(u_lec)
    u_stu = User(
        username=f"stu_sess_{uid}", email=f"stu_sess_{uid}@t.com",
        password_hash=get_password_hash("A"), role=UserRole.student,
        is_active=True, must_change_password=False, is_deleted=False, token_version=1,
    )
    db_session.add(u_stu)
    db_session.flush()

    lec = Lecturer(user_id=u_lec.id, code=f"LEC_SESS_{uid}", full_name="GV Buổi",
                   type=LecturerType.full_time, is_deleted=False)
    db_session.add(lec)
    db_session.flush()

    cls = Class(code=f"CLS_SESS_{uid}", subject_id=sub.id, semester_id=sem.id, lecturer_id=lec.id,
                max_students=30, status=ClassStatus.active, is_deleted=False)
    db_session.add(cls)

    stu = Student(user_id=u_stu.id, student_code=f"SV_SESS_{uid}", full_name="SV Test",
                  status=StudentStatus.studying, is_deleted=False)
    db_session.add(stu)
    db_session.flush()

    # 3 buổi: scheduled, open, closed
    s1 = SessionModel(class_id=cls.id, session_no=1, date=date(2026, 10, 1),
                      start_time=time(8, 0), end_time=time(10, 0), room=f"S_ROOM_{uid}",
                      status=SessionStatus.scheduled)
    s2 = SessionModel(class_id=cls.id, session_no=2, date=date(2026, 10, 8),
                      start_time=time(8, 0), end_time=time(10, 0), room=f"S_ROOM_{uid}",
                      status=SessionStatus.open)
    s3 = SessionModel(class_id=cls.id, session_no=3, date=date(2026, 10, 15),
                      start_time=time(8, 0), end_time=time(10, 0), room=f"S_ROOM_{uid}",
                      status=SessionStatus.closed)
    db_session.add_all([s1, s2, s3])
    db_session.commit()
    for o in [sem, sub, u_admin, u_lec, u_stu, lec, cls, stu, s1, s2, s3]:
        db_session.refresh(o)

    return {"u_admin": u_admin, "u_lec": u_lec, "u_stu": u_stu,
            "cls": cls, "stu": stu, "s1": s1, "s2": s2, "s3": s3}


def test_update_scheduled_session(test_client: TestClient, db_session: Session, sess_data):
    """Sửa ngày/phòng buổi scheduled thành công."""
    d = sess_data
    uid = _uid()
    headers = {"Authorization": f"Bearer {_tok(d['u_admin'])}"}
    resp = test_client.patch(f"/api/v1/sessions/{d['s1'].id}", json={
        "room": f"NEW_ROOM_{uid}",
        "date": "2026-10-03",
    }, headers=headers)
    assert resp.status_code == 200, resp.text
    db_session.expire_all()
    s1 = db_session.query(SessionModel).filter(SessionModel.id == d["s1"].id).first()
    assert s1.room == f"NEW_ROOM_{uid}".upper()  # room bị normalize thành uppercase
    assert s1.date == date(2026, 10, 3)


def test_cannot_update_open_session(test_client: TestClient, db_session: Session, sess_data):
    """Không sửa được buổi open."""
    d = sess_data
    headers = {"Authorization": f"Bearer {_tok(d['u_admin'])}"}
    resp = test_client.patch(f"/api/v1/sessions/{d['s2'].id}", json={"room": "X"}, headers=headers)
    assert resp.status_code == 409
    assert resp.json()["detail"]["code"] == "SESSION_NOT_EDITABLE"


def test_cannot_update_closed_session(test_client: TestClient, db_session: Session, sess_data):
    """Không sửa được buổi closed."""
    d = sess_data
    headers = {"Authorization": f"Bearer {_tok(d['u_admin'])}"}
    resp = test_client.patch(f"/api/v1/sessions/{d['s3'].id}", json={"room": "X"}, headers=headers)
    assert resp.status_code == 409
    assert resp.json()["detail"]["code"] == "SESSION_NOT_EDITABLE"


def test_cancel_session(test_client: TestClient, db_session: Session, sess_data):
    """Hủy buổi scheduled → cancelled, session_no không đánh lại."""
    d = sess_data
    headers = {"Authorization": f"Bearer {_tok(d['u_admin'])}"}
    old_no = d["s1"].session_no
    resp = test_client.post(f"/api/v1/sessions/{d['s1'].id}/cancel", headers=headers)
    assert resp.status_code == 200, resp.text
    db_session.expire_all()
    s1 = db_session.query(SessionModel).filter(SessionModel.id == d["s1"].id).first()
    assert s1.status == SessionStatus.cancelled
    assert s1.session_no == old_no  # không đánh lại


def test_makeup_session(test_client: TestClient, db_session: Session, sess_data):
    """Thêm buổi bù thủ công thành công."""
    d = sess_data
    headers = {"Authorization": f"Bearer {_tok(d['u_admin'])}"}
    resp = test_client.post(f"/api/v1/classes/{d['cls'].id}/sessions", json={
        "date": "2026-11-20",
        "start_time": "14:00:00",
        "end_time": "16:00:00",
        "room": "MAKEUP_ROOM",
    }, headers=headers)
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["schedule_id"] is None  # buổi bù không có schedule


def test_timetable_lecturer(test_client: TestClient, db_session: Session, sess_data):
    """Giảng viên thấy buổi lớp mình dạy trong /me/timetable."""
    d = sess_data
    headers = {"Authorization": f"Bearer {_tok(d['u_lec'])}"}
    resp = test_client.get("/api/v1/me/timetable?from_date=2026-10-01&to_date=2026-10-31", headers=headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["total"] > 0
    assert all(item["class_id"] == d["cls"].id for item in body["items"])


def test_timetable_student(test_client: TestClient, db_session: Session, sess_data):
    """Sinh viên chỉ thấy buổi lớp mình enrolled."""
    d = sess_data
    # Ghi danh sv vào lớp
    cs = ClassStudent(class_id=d["cls"].id, student_id=d["stu"].id, status=ClassStudentStatus.enrolled)
    db_session.add(cs)
    db_session.commit()

    headers = {"Authorization": f"Bearer {_tok(d['u_stu'])}"}
    resp = test_client.get("/api/v1/me/timetable?from_date=2026-10-01&to_date=2026-10-31", headers=headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["total"] > 0


def test_timetable_student_no_unenrolled(test_client: TestClient, db_session: Session, sess_data):
    """Sinh viên không thấy lớp mình không học trong /me/timetable."""
    d = sess_data
    headers = {"Authorization": f"Bearer {_tok(d['u_stu'])}"}
    resp = test_client.get("/api/v1/me/timetable?from_date=2026-10-01&to_date=2026-10-31", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 0  # sv chưa enrolled


def test_admin_timetable(test_client: TestClient, db_session: Session, sess_data, admin_headers):
    """/admin/timetable chỉ admin gọi được."""
    resp = test_client.get(
        "/api/v1/admin/timetable?from_date=2026-10-01&to_date=2026-10-31",
        headers=admin_headers,
    )
    assert resp.status_code == 200


def test_student_cannot_call_admin_timetable(test_client: TestClient, db_session: Session, sess_data):
    """Sinh viên gọi /admin/timetable bị 403."""
    d = sess_data
    headers = {"Authorization": f"Bearer {_tok(d['u_stu'])}"}
    resp = test_client.get("/api/v1/admin/timetable?from_date=2026-10-01&to_date=2026-10-31", headers=headers)
    assert resp.status_code == 403
