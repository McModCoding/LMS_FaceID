"""
test_schedules.py
Kiểm tra tạo lịch, sinh buổi học, xung đột, sửa/xóa lịch.
"""
import uuid
from datetime import date, time

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import create_access_token, get_password_hash
from app.models.class_ import Class, ClassStatus
from app.models.lecturer import Lecturer, LecturerType
from app.models.semester import Semester
from app.models.session import Session as SessionModel
from app.models.session import SessionStatus
from app.models.subject import Subject
from app.models.user import User, UserRole


def _tok(user: User) -> str:
    return create_access_token({"sub": str(user.id), "role": user.role.value, "token_version": user.token_version})


def _uid() -> str:
    return uuid.uuid4().hex[:8]


@pytest.fixture
def sch_data(db_session: Session):
    """Dữ liệu cơ bản cho test lịch học."""
    uid = _uid()
    sem = Semester(name=f"HK_SCH_{uid}", start_date=date(2026, 9, 1), end_date=date(2026, 12, 31))
    db_session.add(sem)
    sub = Subject(code=f"SCH_{uid}", name="Môn Test Lịch", credits=3)
    db_session.add(sub)

    u_admin = User(
        username=f"admin_sch_{uid}", email=f"admin_sch_{uid}@t.com",
        password_hash=get_password_hash("A"), role=UserRole.admin,
        is_active=True, must_change_password=False, is_deleted=False, token_version=1,
    )
    db_session.add(u_admin)

    u_lec = User(
        username=f"lec_sch_{uid}", email=f"lec_sch_{uid}@t.com",
        password_hash=get_password_hash("A"), role=UserRole.lecturer,
        is_active=True, must_change_password=False, is_deleted=False, token_version=1,
    )
    db_session.add(u_lec)

    u_lec2 = User(
        username=f"lec_sch2_{uid}", email=f"lec_sch2_{uid}@t.com",
        password_hash=get_password_hash("A"), role=UserRole.lecturer,
        is_active=True, must_change_password=False, is_deleted=False, token_version=1,
    )
    db_session.add(u_lec2)
    db_session.flush()

    lec = Lecturer(user_id=u_lec.id, code=f"LEC_S1_{uid}", full_name="GV1",
                   type=LecturerType.full_time, is_deleted=False)
    lec2 = Lecturer(user_id=u_lec2.id, code=f"LEC_S2_{uid}", full_name="GV2",
                    type=LecturerType.full_time, is_deleted=False)
    db_session.add_all([lec, lec2])
    db_session.flush()

    cls1 = Class(code=f"CLS1_{uid}", subject_id=sub.id, semester_id=sem.id, lecturer_id=lec.id,
                 max_students=30, status=ClassStatus.active, is_deleted=False)
    cls2 = Class(code=f"CLS2_{uid}", subject_id=sub.id, semester_id=sem.id, lecturer_id=lec2.id,
                 max_students=30, status=ClassStatus.active, is_deleted=False)
    db_session.add_all([cls1, cls2])
    db_session.commit()
    for o in [sem, sub, u_admin, u_lec, u_lec2, lec, lec2, cls1, cls2]:
        db_session.refresh(o)

    return {"sem": sem, "sub": sub, "u_admin": u_admin, "u_lec": u_lec, "u_lec2": u_lec2,
            "lec": lec, "lec2": lec2, "cls1": cls1, "cls2": cls2}


# ---------------------------------------------------------------- Sinh buổi đúng
def test_generate_sessions_correct_count(test_client: TestClient, db_session: Session, sch_data):
    """
    Lịch Thứ Hai (weekday=0), 01/09/2026–28/09/2026.
    01/09/2026 là Thứ Ba → Thứ Hai đầu tiên là 07/09/2026 → 4 buổi (07,14,21,28/09).
    """
    d = sch_data
    headers = {"Authorization": f"Bearer {_tok(d['u_admin'])}"}
    resp = test_client.post(f"/api/v1/classes/{d['cls1'].id}/schedules", json={
        "weekday": 0,
        "start_time": "08:00:00",
        "end_time": "10:00:00",
        "room": "A101",
        "start_date": "2026-09-01",
        "end_date": "2026-09-28",
    }, headers=headers)
    assert resp.status_code == 201, resp.text
    sessions = db_session.query(SessionModel).filter(SessionModel.class_id == d["cls1"].id).all()
    assert len(sessions) == 4
    expected_dates = {date(2026, 9, 7), date(2026, 9, 14), date(2026, 9, 21), date(2026, 9, 28)}
    actual_dates = {s.date for s in sessions}
    assert actual_dates == expected_dates


def test_generate_sessions_correct_weekday(test_client: TestClient, db_session: Session, sch_data):
    """Tất cả buổi sinh ra phải đúng thứ."""
    d = sch_data
    headers = {"Authorization": f"Bearer {_tok(d['u_admin'])}"}
    resp = test_client.post(f"/api/v1/classes/{d['cls1'].id}/schedules", json={
        "weekday": 2,  # Thứ Tư
        "start_time": "13:00:00",
        "end_time": "15:00:00",
        "room": "B202",
        "start_date": "2026-09-01",
        "end_date": "2026-10-31",
    }, headers=headers)
    assert resp.status_code == 201, resp.text
    sessions = db_session.query(SessionModel).filter(
        SessionModel.class_id == d["cls1"].id,
        SessionModel.start_time == time(13, 0),
    ).all()
    assert len(sessions) > 0
    for s in sessions:
        assert s.date.weekday() == 2, f"Ngày {s.date} không phải Thứ Tư"


def test_schedule_outside_semester_rejected(test_client: TestClient, db_session: Session, sch_data):
    """Lịch ngoài khoảng học kỳ bị từ chối."""
    d = sch_data
    headers = {"Authorization": f"Bearer {_tok(d['u_admin'])}"}
    resp = test_client.post(f"/api/v1/classes/{d['cls1'].id}/schedules", json={
        "weekday": 1,
        "start_time": "08:00:00",
        "end_time": "10:00:00",
        "room": "C303",
        "start_date": "2026-08-01",  # trước học kỳ
        "end_date": "2026-09-30",
    }, headers=headers)
    assert resp.status_code == 422
    assert resp.json()["detail"]["code"] == "DATE_OUT_OF_SEMESTER"


# ---------------------------------------------------------------- Xung đột phòng
def test_room_conflict_rejected(test_client: TestClient, db_session: Session, sch_data):
    """Trùng phòng, cùng ngày, giờ giao nhau → 409."""
    d = sch_data
    headers = {"Authorization": f"Bearer {_tok(d['u_admin'])}"}
    uid = _uid()
    room = f"ROOM_{uid}"
    # Tạo lịch cls1
    test_client.post(f"/api/v1/classes/{d['cls1'].id}/schedules", json={
        "weekday": 1,
        "start_time": "08:00:00",
        "end_time": "10:00:00",
        "room": room,
        "start_date": "2026-10-01",
        "end_date": "2026-10-31",
    }, headers=headers)
    # cls2 cùng phòng, giờ giao nhau → xung đột
    resp = test_client.post(f"/api/v1/classes/{d['cls2'].id}/schedules", json={
        "weekday": 1,
        "start_time": "09:00:00",
        "end_time": "11:00:00",
        "room": room.lower(),  # cùng phòng sau uppercase
        "start_date": "2026-10-01",
        "end_date": "2026-10-31",
    }, headers=headers)
    assert resp.status_code == 409
    detail = resp.json()["detail"]
    assert detail["code"] == "SCHEDULE_CONFLICT"
    assert any(c["conflict_type"] == "room" for c in detail["details"]["conflicts"])


def test_boundary_no_conflict(test_client: TestClient, db_session: Session, sch_data):
    """Kết thúc 09:00 và bắt đầu 09:00 KHÔNG xung đột."""
    d = sch_data
    headers = {"Authorization": f"Bearer {_tok(d['u_admin'])}"}
    uid = _uid()
    room = f"BNDRY_{uid}"
    test_client.post(f"/api/v1/classes/{d['cls1'].id}/schedules", json={
        "weekday": 3,
        "start_time": "07:00:00",
        "end_time": "09:00:00",
        "room": room,
        "start_date": "2026-10-01",
        "end_date": "2026-10-31",
    }, headers=headers)
    resp = test_client.post(f"/api/v1/classes/{d['cls2'].id}/schedules", json={
        "weekday": 3,
        "start_time": "09:00:00",
        "end_time": "11:00:00",
        "room": room,
        "start_date": "2026-10-01",
        "end_date": "2026-10-31",
    }, headers=headers)
    assert resp.status_code == 201, resp.text  # Không xung đột


# ---------------------------------------------------------------- Xung đột giảng viên
def test_lecturer_conflict_rejected(test_client: TestClient, db_session: Session, sch_data):
    """Cùng giảng viên, cùng ngày, giờ giao nhau → 409."""
    d = sch_data
    uid = _uid()
    # Tạo lớp thứ 3 cùng lec với cls1
    cls3 = Class(code=f"CLS3_{uid}", subject_id=d["sub"].id, semester_id=d["sem"].id,
                 lecturer_id=d["lec"].id, max_students=30, status=ClassStatus.active, is_deleted=False)
    db_session.add(cls3)
    db_session.commit()
    db_session.refresh(cls3)

    headers = {"Authorization": f"Bearer {_tok(d['u_admin'])}"}
    test_client.post(f"/api/v1/classes/{d['cls1'].id}/schedules", json={
        "weekday": 4,
        "start_time": "08:00:00",
        "end_time": "10:00:00",
        "room": f"LEC1_{uid}",
        "start_date": "2026-10-01",
        "end_date": "2026-10-31",
    }, headers=headers)
    resp = test_client.post(f"/api/v1/classes/{cls3.id}/schedules", json={
        "weekday": 4,
        "start_time": "09:00:00",
        "end_time": "11:00:00",
        "room": f"LEC2_{uid}",  # phòng khác nhưng cùng GV
        "start_date": "2026-10-01",
        "end_date": "2026-10-31",
    }, headers=headers)
    assert resp.status_code == 409
    detail = resp.json()["detail"]
    assert detail["code"] == "SCHEDULE_CONFLICT"
    assert any(c["conflict_type"] == "lecturer" for c in detail["details"]["conflicts"])


def test_conflict_no_sessions_created(test_client: TestClient, db_session: Session, sch_data):
    """Tạo lịch xung đột → không có buổi nào được tạo."""
    d = sch_data
    headers = {"Authorization": f"Bearer {_tok(d['u_admin'])}"}
    uid = _uid()
    room = f"ATOMIC_{uid}"
    test_client.post(f"/api/v1/classes/{d['cls1'].id}/schedules", json={
        "weekday": 5,
        "start_time": "10:00:00",
        "end_time": "12:00:00",
        "room": room,
        "start_date": "2026-10-01",
        "end_date": "2026-10-31",
    }, headers=headers)
    count_before = db_session.query(SessionModel).filter(SessionModel.class_id == d["cls2"].id).count()
    resp = test_client.post(f"/api/v1/classes/{d['cls2'].id}/schedules", json={
        "weekday": 5,
        "start_time": "11:00:00",
        "end_time": "13:00:00",
        "room": room,
        "start_date": "2026-10-01",
        "end_date": "2026-10-31",
    }, headers=headers)
    assert resp.status_code == 409
    count_after = db_session.query(SessionModel).filter(SessionModel.class_id == d["cls2"].id).count()
    assert count_after == count_before  # không tạo buổi nào


def test_cancelled_session_no_conflict(test_client: TestClient, db_session: Session, sch_data):
    """Buổi đã cancelled không gây xung đột."""
    d = sch_data
    headers = {"Authorization": f"Bearer {_tok(d['u_admin'])}"}
    uid = _uid()
    room = f"CANCEL_{uid}"
    test_client.post(f"/api/v1/classes/{d['cls1'].id}/schedules", json={
        "weekday": 6,
        "start_time": "08:00:00",
        "end_time": "10:00:00",
        "room": room,
        "start_date": "2026-11-01",
        "end_date": "2026-11-30",
    }, headers=headers)
    # Hủy tất cả buổi của cls1 trong tháng 11
    db_session.expire_all()
    sessions = db_session.query(SessionModel).filter(
        SessionModel.class_id == d["cls1"].id,
        SessionModel.room == room.upper(),
    ).all()
    for s in sessions:
        s.status = SessionStatus.cancelled
    db_session.commit()

    # cls2 cùng phòng, cùng giờ → không xung đột vì cls1 đã cancelled
    resp = test_client.post(f"/api/v1/classes/{d['cls2'].id}/schedules", json={
        "weekday": 6,
        "start_time": "09:00:00",
        "end_time": "11:00:00",
        "room": room,
        "start_date": "2026-11-01",
        "end_date": "2026-11-30",
    }, headers=headers)
    assert resp.status_code == 201, resp.text


def test_update_schedule_no_touch_open_sessions(test_client: TestClient, db_session: Session, sch_data):
    """Sửa lịch không đụng buổi open/closed."""
    d = sch_data
    headers = {"Authorization": f"Bearer {_tok(d['u_admin'])}"}
    uid = _uid()
    room = f"EDIT_{uid}"
    resp = test_client.post(f"/api/v1/classes/{d['cls1'].id}/schedules", json={
        "weekday": 0,
        "start_time": "08:00:00",
        "end_time": "10:00:00",
        "room": room,
        "start_date": "2026-09-01",
        "end_date": "2026-09-30",
    }, headers=headers)
    assert resp.status_code == 201, resp.text
    sch_id = resp.json()["id"]
    # Đặt buổi đầu tiên thành open
    db_session.expire_all()
    sess = db_session.query(SessionModel).filter(
        SessionModel.class_id == d["cls1"].id,
        SessionModel.room == room.upper(),
    ).order_by(SessionModel.date.asc()).first()
    open_session_id = sess.id
    orig_room = sess.room
    sess.status = SessionStatus.open
    db_session.commit()

    # Sửa lịch
    resp2 = test_client.patch(f"/api/v1/classes/{d['cls1'].id}/schedules/{sch_id}", json={
        "room": f"EDIT_NEW_{uid}",
    }, headers=headers)
    assert resp2.status_code == 200

    # Buổi open phải còn nguyên — không bị đổi room
    db_session.expire_all()
    open_sess_after = db_session.query(SessionModel).filter(SessionModel.id == open_session_id).first()
    assert open_sess_after.status == SessionStatus.open
    assert open_sess_after.room == orig_room  # không bị đổi
    all_sessions = db_session.query(SessionModel).filter(SessionModel.schedule_id == sch_id).all()
    assert len(all_sessions) == 4
    assert len({s.date for s in all_sessions}) == 4


def test_same_class_overlapping_schedule_rejected(test_client, db_session, sch_data):
    d = sch_data
    auth = {"Authorization": f"Bearer {_tok(d['u_admin'])}"}
    endpoint = f"/api/v1/classes/{d['cls1'].id}/schedules"
    payload = {"weekday": 0, "start_time": "18:00", "end_time": "19:00",
               "room": f"SAME_{_uid()}", "start_date": "2026-09-07", "end_date": "2026-09-07"}
    first = test_client.post(endpoint, json=payload, headers=auth)
    assert first.status_code == 201
    for room in [payload["room"], payload["room"] + "_OTHER"]:
        conflict = test_client.post(endpoint, json={**payload, "room": room}, headers=auth)
        assert conflict.status_code == 409
        assert conflict.json()["detail"]["code"] == "SCHEDULE_CONFLICT"
    assert db_session.query(SessionModel).filter(SessionModel.class_id == d["cls1"].id).count() == 1
    adjacent = test_client.post(endpoint, json={**payload, "start_time": "19:00", "end_time": "20:00"}, headers=auth)
    assert adjacent.status_code == 201
    unchanged = test_client.patch(endpoint + f"/{first.json()['id']}", json={"room": payload["room"]}, headers=auth)
    assert unchanged.status_code == 200


def test_schedule_weekday_change_does_not_recreate_processed_history(test_client, db_session, sch_data):
    d = sch_data
    auth = {"Authorization": f"Bearer {_tok(d['u_admin'])}"}
    endpoint = f"/api/v1/classes/{d['cls1'].id}/schedules"
    first = test_client.post(endpoint, headers=auth, json={
        "weekday": 0, "start_time": "18:00", "end_time": "19:00", "room": f"HISTORY_{_uid()}",
        "start_date": "2026-09-01", "end_date": "2026-09-30",
    })
    assert first.status_code == 201
    schedule_id = first.json()["id"]
    rows = db_session.query(SessionModel).filter_by(schedule_id=schedule_id).order_by(SessionModel.date).all()
    rows[0].status = SessionStatus.closed
    rows[1].status = SessionStatus.open
    preserved_ids = [rows[0].id, rows[1].id]
    db_session.commit()
    response = test_client.patch(endpoint + f"/{schedule_id}", headers=auth, json={"weekday": 1})
    assert response.status_code == 200
    db_session.expire_all()
    kept = db_session.query(SessionModel).filter(SessionModel.id.in_(preserved_ids)).all()
    assert {row.status for row in kept} == {SessionStatus.open, SessionStatus.closed}
    rebuilt = db_session.query(SessionModel).filter_by(schedule_id=schedule_id, status=SessionStatus.scheduled).all()
    assert all(row.date > date(2026, 9, 14) for row in rebuilt)
