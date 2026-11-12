"""
test_enrollment.py
Kiểm tra ghi danh, rút, thêm lại, sức chứa, xung đột sinh viên.
"""
import uuid
from datetime import date, time
from io import BytesIO

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
def enr_data(db_session: Session):
    uid = _uid()
    sem = Semester(name=f"HK_ENR_{uid}", start_date=date(2026, 9, 1), end_date=date(2026, 12, 31))
    db_session.add(sem)
    sub = Subject(code=f"ENR_{uid}", name="Môn Ghi Danh", credits=3)
    db_session.add(sub)

    u_admin = User(
        username=f"admin_enr_{uid}", email=f"admin_enr_{uid}@t.com",
        password_hash=get_password_hash("A"), role=UserRole.admin,
        is_active=True, must_change_password=False, is_deleted=False, token_version=1,
    )
    db_session.add(u_admin)
    u_lec = User(
        username=f"lec_enr_{uid}", email=f"lec_enr_{uid}@t.com",
        password_hash=get_password_hash("A"), role=UserRole.lecturer,
        is_active=True, must_change_password=False, is_deleted=False, token_version=1,
    )
    db_session.add(u_lec)
    db_session.flush()

    lec = Lecturer(user_id=u_lec.id, code=f"LEC_ENR_{uid}", full_name="GV Ghi Danh",
                   type=LecturerType.full_time, is_deleted=False)
    db_session.add(lec)
    db_session.flush()

    cls = Class(code=f"CLS_ENR_{uid}", subject_id=sub.id, semester_id=sem.id, lecturer_id=lec.id,
                max_students=3, status=ClassStatus.active, is_deleted=False)
    db_session.add(cls)

    # Tạo 4 sinh viên — mỗi lần fixture chạy đều dùng uid riêng
    students = []
    for i in range(4):
        us = User(
            username=f"sv_enr_{uid}_{i}", email=f"sv_enr_{uid}_{i}@t.com",
            password_hash=get_password_hash("A"), role=UserRole.student,
            is_active=True, must_change_password=False, is_deleted=False, token_version=1,
        )
        db_session.add(us)
        db_session.flush()
        st = Student(user_id=us.id, student_code=f"SV_ENR_{uid}_{i}", full_name=f"SV {i}",
                     status=StudentStatus.studying, is_deleted=False)
        db_session.add(st)
        students.append(st)

    # SV trạng thái suspended
    sus_uid = _uid()
    us_sus = User(
        username=f"sv_sus_{sus_uid}", email=f"sv_sus_{sus_uid}@t.com",
        password_hash=get_password_hash("A"), role=UserRole.student,
        is_active=True, must_change_password=False, is_deleted=False, token_version=1,
    )
    db_session.add(us_sus)
    db_session.flush()
    st_sus = Student(user_id=us_sus.id, student_code=f"SV_SUS_{sus_uid}", full_name="SV Suspended",
                     status=StudentStatus.suspended, is_deleted=False)
    db_session.add(st_sus)

    db_session.commit()
    for o in [sem, sub, u_admin, u_lec, lec, cls, *students, st_sus]:
        db_session.refresh(o)

    return {
        "sem": sem, "sub": sub, "u_admin": u_admin, "cls": cls,
        "students": students, "st_sus": st_sus,
    }


def test_enroll_student_success(test_client: TestClient, db_session: Session, enr_data):
    d = enr_data
    headers = {"Authorization": f"Bearer {_tok(d['u_admin'])}"}
    resp = test_client.post(f"/api/v1/classes/{d['cls'].id}/students", json={
        "student_ids": [d["students"][0].id]
    }, headers=headers)
    assert resp.status_code == 200, resp.text
    db_session.expire_all()
    cs = db_session.query(ClassStudent).filter(
        ClassStudent.class_id == d["cls"].id,
        ClassStudent.student_id == d["students"][0].id,
    ).first()
    assert cs is not None
    assert cs.status == ClassStudentStatus.enrolled


def test_enroll_suspended_student_rejected(test_client: TestClient, db_session: Session, enr_data):
    """Chỉ sinh viên studying mới ghi danh được."""
    d = enr_data
    headers = {"Authorization": f"Bearer {_tok(d['u_admin'])}"}
    resp = test_client.post(f"/api/v1/classes/{d['cls'].id}/students", json={
        "student_ids": [d["st_sus"].id]
    }, headers=headers)
    assert resp.status_code == 422
    assert resp.json()["detail"]["code"] == "STUDENT_NOT_STUDYING"


def test_class_capacity_limit(test_client: TestClient, db_session: Session, enr_data):
    """Không vượt max_students (max=3)."""
    d = enr_data
    headers = {"Authorization": f"Bearer {_tok(d['u_admin'])}"}
    # Thêm 3 sv (max)
    for i in range(3):
        resp = test_client.post(f"/api/v1/classes/{d['cls'].id}/students", json={
            "student_ids": [d["students"][i].id]
        }, headers=headers)
        assert resp.status_code == 200, f"student {i}: {resp.text}"
    # Không thể giảm sĩ số xuống thấp hơn số sinh viên đang thuộc lớp.
    resize = test_client.patch(
        f"/api/v1/classes/{d['cls'].id}", json={"max_students": 2}, headers=headers
    )
    assert resize.status_code == 422
    assert resize.json()["detail"]["code"] == "MAX_STUDENTS_BELOW_ENROLLED"
    # Thêm sv thứ 4 → bị từ chối
    resp4 = test_client.post(f"/api/v1/classes/{d['cls'].id}/students", json={
        "student_ids": [d["students"][3].id]
    }, headers=headers)
    assert resp4.status_code == 409
    assert resp4.json()["detail"]["code"] == "CLASS_FULL"


def test_confirm_import_revalidates_students_and_capacity(
    test_client: TestClient, db_session: Session, enr_data
):
    """Xác nhận import không được tin dữ liệu xem trước do client gửi lại."""
    d = enr_data
    headers = {"Authorization": f"Bearer {_tok(d['u_admin'])}"}
    url = f"/api/v1/classes/{d['cls'].id}/students/import/confirm"

    # Client không thể đưa sinh viên đã bị tạm dừng vào valid_rows.
    suspended = test_client.post(
        url, json={"valid_rows": [{"student_id": d["st_sus"].id}]}, headers=headers
    )
    assert suspended.status_code == 422
    assert suspended.json()["detail"]["code"] == "STUDENT_NOT_STUDYING"

    # Một request vượt sĩ số phải bị từ chối toàn bộ, không ghi danh một phần.
    full = test_client.post(
        url,
        json={"valid_rows": [{"student_id": student.id} for student in d["students"]]},
        headers=headers,
    )
    assert full.status_code == 409
    assert full.json()["detail"]["code"] == "CLASS_FULL"
    assert (
        db_session.query(ClassStudent)
        .filter(
            ClassStudent.class_id == d["cls"].id,
            ClassStudent.status == ClassStudentStatus.enrolled,
        )
        .count()
        == 0
    )


def test_import_preview_uses_consistent_fields_and_marks_duplicate_rows(
    test_client: TestClient, enr_data
):
    """Preview trả đúng field cho frontend và không coi MSSV lặp là hợp lệ."""
    from openpyxl import Workbook

    d = enr_data
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(["student_code"])
    sheet.append([d["students"][0].student_code])
    sheet.append([d["students"][0].student_code])
    sheet.append([d["st_sus"].student_code])
    file_bytes = BytesIO()
    workbook.save(file_bytes)

    headers = {"Authorization": f"Bearer {_tok(d['u_admin'])}"}
    response = test_client.post(
        f"/api/v1/classes/{d['cls'].id}/students/import/preview",
        files={
            "file": (
                "enrollment.xlsx",
                file_bytes.getvalue(),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
        headers=headers,
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["valid_count"] == 1
    assert payload["warning_count"] == 1
    assert payload["error_count"] == 1
    assert payload["valid_rows"][0]["student_code"] == d["students"][0].student_code


def test_confirm_import_revalidates_schedule_conflict(
    test_client: TestClient, db_session: Session, enr_data
):
    """Xung đột phát sinh sau preview vẫn phải chặn ở bước xác nhận."""
    d = enr_data
    headers = {"Authorization": f"Bearer {_tok(d['u_admin'])}"}
    student = d["students"][0]
    uid = _uid()

    other_class = Class(
        code=f"CLS_IMPORT_CONFLICT_{uid}",
        subject_id=d["sub"].id,
        semester_id=d["sem"].id,
        max_students=30,
        status=ClassStatus.active,
        is_deleted=False,
    )
    db_session.add(other_class)
    db_session.flush()
    db_session.add(ClassStudent(
        class_id=other_class.id,
        student_id=student.id,
        status=ClassStudentStatus.enrolled,
    ))
    db_session.add_all([
        SessionModel(
            class_id=other_class.id,
            schedule_id=None,
            session_no=1,
            date=date(2027, 1, 5),
            start_time=time(8, 0),
            end_time=time(10, 0),
            room="ROOM_X",
            status=SessionStatus.scheduled,
        ),
        SessionModel(
            class_id=d["cls"].id,
            schedule_id=None,
            session_no=1,
            date=date(2027, 1, 5),
            start_time=time(9, 0),
            end_time=time(11, 0),
            room="ROOM_Y",
            status=SessionStatus.scheduled,
        ),
    ])
    db_session.commit()

    response = test_client.post(
        f"/api/v1/classes/{d['cls'].id}/students/import/confirm",
        json={"valid_rows": [{"student_id": student.id}]},
        headers=headers,
    )
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "SCHEDULE_CONFLICT"
    assert not db_session.query(ClassStudent).filter(
        ClassStudent.class_id == d["cls"].id,
        ClassStudent.student_id == student.id,
    ).first()


def test_drop_and_reenroll(test_client: TestClient, db_session: Session, enr_data):
    """Rút sinh viên = dropped; thêm lại → enrolled."""
    d = enr_data
    headers = {"Authorization": f"Bearer {_tok(d['u_admin'])}"}
    stu = d["students"][0]
    # Ghi danh
    test_client.post(f"/api/v1/classes/{d['cls'].id}/students", json={"student_ids": [stu.id]}, headers=headers)
    # Rút
    resp = test_client.delete(f"/api/v1/classes/{d['cls'].id}/students/{stu.id}", headers=headers)
    assert resp.status_code == 204
    db_session.expire_all()
    cs = db_session.query(ClassStudent).filter(
        ClassStudent.class_id == d["cls"].id, ClassStudent.student_id == stu.id
    ).first()
    assert cs is not None
    assert cs.status == ClassStudentStatus.dropped
    # Thêm lại
    resp2 = test_client.post(f"/api/v1/classes/{d['cls'].id}/students", json={"student_ids": [stu.id]}, headers=headers)
    assert resp2.status_code == 200
    db_session.expire_all()
    cs2 = db_session.query(ClassStudent).filter(
        ClassStudent.class_id == d["cls"].id, ClassStudent.student_id == stu.id
    ).first()
    assert cs2.status == ClassStudentStatus.enrolled


def test_student_conflict_on_enrollment(test_client: TestClient, db_session: Session, enr_data):
    """Sinh viên ghi danh vào lớp trùng giờ với lớp đang học → 409."""
    d = enr_data
    headers = {"Authorization": f"Bearer {_tok(d['u_admin'])}"}
    stu = d["students"][0]
    uid = _uid()

    # Tạo lớp 2 với buổi học
    cls2 = Class(code=f"CLS_ENR2_{uid}", subject_id=d["sub"].id, semester_id=d["sem"].id,
                 max_students=30, status=ClassStatus.active, is_deleted=False)
    db_session.add(cls2)
    db_session.flush()

    # Ghi danh sv vào cls2
    cs2 = ClassStudent(class_id=cls2.id, student_id=stu.id, status=ClassStudentStatus.enrolled)
    db_session.add(cs2)

    # Tạo buổi học cho cls2 (ngày tương lai)
    sess2 = SessionModel(
        class_id=cls2.id, schedule_id=None, session_no=1,
        date=date(2027, 1, 5), start_time=time(8, 0), end_time=time(10, 0),
        room="ROOM_X", status=SessionStatus.scheduled,
    )
    db_session.add(sess2)

    # Tạo buổi học cho cls1 cùng ngày, giờ giao nhau
    sess1 = SessionModel(
        class_id=d["cls"].id, schedule_id=None, session_no=1,
        date=date(2027, 1, 5), start_time=time(9, 0), end_time=time(11, 0),
        room="ROOM_Y", status=SessionStatus.scheduled,
    )
    db_session.add(sess1)
    db_session.commit()

    # Cố ghi danh sv vào cls1 → xung đột
    resp = test_client.post(f"/api/v1/classes/{d['cls'].id}/students", json={"student_ids": [stu.id]}, headers=headers)
    assert resp.status_code == 409
    assert resp.json()["detail"]["code"] == "SCHEDULE_CONFLICT"
