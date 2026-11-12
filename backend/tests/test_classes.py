"""
test_classes.py
Kiểm tra CRUD lớp, kích hoạt, đóng, xóa và phân quyền.
"""
import uuid
from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import create_access_token, get_password_hash
from app.models.class_ import Class, ClassStatus, ClassStudent, ClassStudentStatus
from app.models.lecturer import Lecturer, LecturerType
from app.models.semester import Semester
from app.models.student import Student, StudentStatus
from app.models.subject import Subject
from app.models.user import User, UserRole


def _uid() -> str:
    return uuid.uuid4().hex[:8]


# ----------------------------------------------------------------- Fixtures
@pytest.fixture
def base_data(db_session: Session):
    """Tạo dữ liệu cơ bản: semester, subject, lecturer, student."""
    uid = _uid()
    sem = Semester(name=f"HK1_{uid}", start_date=date(2026, 9, 1), end_date=date(2026, 12, 31))
    db_session.add(sem)
    sub = Subject(code=f"CLS_{uid}", name="Lập trình cơ bản", credits=3)
    db_session.add(sub)

    user_lec = User(
        username=f"lec_{uid}", email=f"lec_{uid}@test.com",
        password_hash=get_password_hash("Test@123"), role=UserRole.lecturer,
        is_active=True, must_change_password=False, is_deleted=False, token_version=1,
    )
    db_session.add(user_lec)
    db_session.flush()

    lec = Lecturer(user_id=user_lec.id, code=f"LEC_{uid}", full_name="Giảng Viên Test",
                   type=LecturerType.full_time, is_deleted=False)
    db_session.add(lec)

    user_lec2 = User(
        username=f"lec2_{uid}", email=f"lec2_{uid}@test.com",
        password_hash=get_password_hash("Test@123"), role=UserRole.lecturer,
        is_active=True, must_change_password=False, is_deleted=False, token_version=1,
    )
    db_session.add(user_lec2)
    db_session.flush()
    lec2 = Lecturer(user_id=user_lec2.id, code=f"LEC2_{uid}", full_name="Giảng Viên 2",
                    type=LecturerType.full_time, is_deleted=False)
    db_session.add(lec2)

    user_stu = User(
        username=f"stu_{uid}", email=f"stu_{uid}@test.com",
        password_hash=get_password_hash("Test@123"), role=UserRole.student,
        is_active=True, must_change_password=False, is_deleted=False, token_version=1,
    )
    db_session.add(user_stu)
    db_session.flush()
    stu = Student(user_id=user_stu.id, student_code=f"SV_CLS_{uid}", full_name="Sinh Viên Test",
                  status=StudentStatus.studying, is_deleted=False)
    db_session.add(stu)
    db_session.commit()
    for o in [sem, sub, lec, lec2, stu, user_lec, user_lec2, user_stu]:
        db_session.refresh(o)
    return {
        "sem": sem, "sub": sub,
        "lec": lec, "lec2": lec2,
        "user_lec": user_lec, "user_lec2": user_lec2,
        "stu": stu, "user_stu": user_stu,
    }


def _make_token(user: User) -> str:
    return create_access_token({"sub": str(user.id), "role": user.role.value, "token_version": user.token_version})


def _admin_headers(db_session: Session) -> dict:
    uid = _uid()
    admin = User(
        username=f"admin_cls_{uid}", email=f"admin_cls_{uid}@test.com",
        password_hash=get_password_hash("Admin@123"), role=UserRole.admin,
        is_active=True, must_change_password=False, is_deleted=False, token_version=1,
    )
    db_session.add(admin)
    db_session.commit()
    db_session.refresh(admin)
    return {"Authorization": f"Bearer {_make_token(admin)}"}


# ----------------------------------------------------------------- Tests: CRUD
def test_create_class(test_client: TestClient, db_session: Session, base_data):
    headers = _admin_headers(db_session)
    data = base_data
    uid = _uid()
    resp = test_client.post("/api/v1/classes", json={
        "code": f"CLS_{uid}",
        "subject_id": data["sub"].id,
        "semester_id": data["sem"].id,
        "max_students": 30,
    }, headers=headers)
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["status"] == "draft"


def test_create_class_duplicate_code(test_client: TestClient, db_session: Session, base_data):
    headers = _admin_headers(db_session)
    data = base_data
    uid = _uid()
    payload = {"code": f"DUP_{uid}", "subject_id": data["sub"].id, "semester_id": data["sem"].id}
    test_client.post("/api/v1/classes", json=payload, headers=headers)
    resp = test_client.post("/api/v1/classes", json=payload, headers=headers)
    assert resp.status_code == 400
    assert resp.json()["detail"]["code"] == "CLASS_CODE_EXISTS"


def test_activate_class_missing_lecturer(test_client: TestClient, db_session: Session, base_data):
    """Kích hoạt lớp thiếu giảng viên bị từ chối."""
    headers = _admin_headers(db_session)
    data = base_data
    uid = _uid()
    resp = test_client.post("/api/v1/classes", json={
        "code": f"NOLEC_{uid}",
        "subject_id": data["sub"].id,
        "semester_id": data["sem"].id,
    }, headers=headers)
    cls_id = resp.json()["id"]
    resp2 = test_client.post(f"/api/v1/classes/{cls_id}/activate", headers=headers)
    assert resp2.status_code == 422
    assert resp2.json()["detail"]["code"] == "MISSING_LECTURER"


def test_activate_class_missing_schedule(test_client: TestClient, db_session: Session, base_data):
    """Kích hoạt lớp có giảng viên nhưng chưa có lịch bị từ chối."""
    headers = _admin_headers(db_session)
    data = base_data
    uid = _uid()
    resp = test_client.post("/api/v1/classes", json={
        "code": f"NOSCH_{uid}",
        "subject_id": data["sub"].id,
        "semester_id": data["sem"].id,
        "lecturer_id": data["lec"].id,
    }, headers=headers)
    cls_id = resp.json()["id"]
    resp2 = test_client.post(f"/api/v1/classes/{cls_id}/activate", headers=headers)
    assert resp2.status_code == 422
    assert resp2.json()["detail"]["code"] == "MISSING_SCHEDULE"


def test_closed_class_not_editable(test_client: TestClient, db_session: Session, base_data):
    """Lớp closed không sửa được."""
    headers = _admin_headers(db_session)
    data = base_data
    uid = _uid()
    cls = Class(
        code=f"CLOSED_{uid}", subject_id=data["sub"].id, semester_id=data["sem"].id,
        lecturer_id=data["lec"].id, max_students=30, status=ClassStatus.closed, is_deleted=False,
    )
    db_session.add(cls)
    db_session.commit()
    db_session.refresh(cls)
    resp = test_client.patch(f"/api/v1/classes/{cls.id}", json={"max_students": 40}, headers=headers)
    assert resp.status_code == 409
    assert resp.json()["detail"]["code"] == "CLASS_CLOSED"


def test_class_update_keeps_valid_attendance_thresholds(
    test_client: TestClient, db_session: Session, base_data
):
    """Patch một ngưỡng vẫn phải được so với ngưỡng hiện có của lớp."""
    headers = _admin_headers(db_session)
    data = base_data
    uid = _uid()
    cls = Class(
        code=f"THRESHOLD_{uid}",
        subject_id=data["sub"].id,
        semester_id=data["sem"].id,
        max_students=30,
        late_after_min=10,
        absent_after_min=30,
        status=ClassStatus.draft,
        is_deleted=False,
    )
    db_session.add(cls)
    db_session.commit()
    db_session.refresh(cls)

    response = test_client.patch(
        f"/api/v1/classes/{cls.id}", json={"late_after_min": 30}, headers=headers
    )
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "INVALID_ATTENDANCE_THRESHOLD"


def test_delete_class_with_students_rejected(test_client: TestClient, db_session: Session, base_data):
    """Xóa lớp đã có sinh viên bị từ chối."""
    headers = _admin_headers(db_session)
    data = base_data
    uid = _uid()
    cls = Class(
        code=f"HASSTUD_{uid}", subject_id=data["sub"].id, semester_id=data["sem"].id,
        max_students=30, status=ClassStatus.draft, is_deleted=False,
    )
    db_session.add(cls)
    db_session.flush()
    cs = ClassStudent(class_id=cls.id, student_id=data["stu"].id, status=ClassStudentStatus.enrolled)
    db_session.add(cs)
    db_session.commit()
    db_session.refresh(cls)
    resp = test_client.delete(f"/api/v1/classes/{cls.id}", headers=headers)
    assert resp.status_code == 409
    assert resp.json()["detail"]["code"] == "CLASS_HAS_STUDENTS"


# ----------------------------------------------------------------- Tests: Phân quyền
def test_lecturer_cannot_see_other_class(test_client: TestClient, db_session: Session, base_data):
    """Giảng viên A không xem được lớp của giảng viên B."""
    data = base_data
    uid = _uid()
    # Tạo lớp thuộc lec
    cls = Class(
        code=f"OWNLEC_{uid}", subject_id=data["sub"].id, semester_id=data["sem"].id,
        lecturer_id=data["lec"].id, max_students=30, status=ClassStatus.draft, is_deleted=False,
    )
    db_session.add(cls)
    db_session.commit()
    db_session.refresh(cls)
    # lec2 cố xem
    headers = {"Authorization": f"Bearer {_make_token(data['user_lec2'])}"}
    resp = test_client.get(f"/api/v1/classes/{cls.id}", headers=headers)
    assert resp.status_code == 403


def test_student_cannot_see_unenrolled_class(test_client: TestClient, db_session: Session, base_data):
    """Sinh viên không xem được lớp mình không học."""
    data = base_data
    uid = _uid()
    cls = Class(
        code=f"SVNOACC_{uid}", subject_id=data["sub"].id, semester_id=data["sem"].id,
        max_students=30, status=ClassStatus.draft, is_deleted=False,
    )
    db_session.add(cls)
    db_session.commit()
    db_session.refresh(cls)
    headers = {"Authorization": f"Bearer {_make_token(data['user_stu'])}"}
    resp = test_client.get(f"/api/v1/classes/{cls.id}", headers=headers)
    assert resp.status_code == 403


def test_student_cannot_see_student_list(test_client: TestClient, db_session: Session, base_data):
    """Sinh viên không xem được danh sách sinh viên khác."""
    data = base_data
    uid = _uid()
    cls = Class(
        code=f"SVNOLIST_{uid}", subject_id=data["sub"].id, semester_id=data["sem"].id,
        max_students=30, status=ClassStatus.draft, is_deleted=False,
    )
    db_session.add(cls)
    db_session.flush()
    cs = ClassStudent(class_id=cls.id, student_id=data["stu"].id, status=ClassStudentStatus.enrolled)
    db_session.add(cs)
    db_session.commit()
    db_session.refresh(cls)
    headers = {"Authorization": f"Bearer {_make_token(data['user_stu'])}"}
    resp = test_client.get(f"/api/v1/classes/{cls.id}/students", headers=headers)
    assert resp.status_code == 403


def test_student_cannot_create_class(test_client: TestClient, db_session: Session, base_data):
    """Sinh viên gọi API tạo lớp bị 403."""
    data = base_data
    uid = _uid()
    headers = {"Authorization": f"Bearer {_make_token(data['user_stu'])}"}
    resp = test_client.post("/api/v1/classes", json={
        "code": f"SVCREATE_{uid}", "subject_id": data["sub"].id, "semester_id": data["sem"].id,
    }, headers=headers)
    assert resp.status_code == 403


def test_lecturer_cannot_create_class(test_client: TestClient, db_session: Session, base_data):
    """Giảng viên gọi API tạo lớp bị 403."""
    data = base_data
    uid = _uid()
    headers = {"Authorization": f"Bearer {_make_token(data['user_lec'])}"}
    resp = test_client.post("/api/v1/classes", json={
        "code": f"LECCREATE_{uid}", "subject_id": data["sub"].id, "semester_id": data["sem"].id,
    }, headers=headers)
    assert resp.status_code == 403


@pytest.fixture
def paginated_classes(db_session, base_data):
    """Unrelated classes sort before all of the student's enrolled classes."""
    data = base_data
    prefix = f"F01_{_uid()}"
    rows = []
    for index in range(17):
        row = Class(
            code=f"{prefix}_{index:02}", subject_id=data["sub"].id,
            semester_id=data["sem"].id, lecturer_id=data["lec"].id,
            status=ClassStatus.active, is_deleted=index == 16,
        )
        db_session.add(row)
        rows.append(row)
    db_session.flush()
    # 0..11 unrelated; 12..14 enrolled; 15 dropped; 16 soft-deleted.
    for index in range(12, 17):
        db_session.add(ClassStudent(
            class_id=rows[index].id, student_id=data["stu"].id,
            status=ClassStudentStatus.dropped if index == 15 else ClassStudentStatus.enrolled,
        ))
    db_session.commit()
    return {"prefix": prefix, "rows": rows, "headers": {
        "Authorization": f"Bearer {_make_token(data['user_stu'])}",
    }}


def test_student_class_pagination_scopes_before_count_and_limit(
    test_client, paginated_classes,
):
    data = paginated_classes
    expected = [row.id for row in data["rows"][12:15]]
    for page, ids in [(1, expected[:2]), (2, expected[2:]), (3, [])]:
        response = test_client.get("/api/v1/classes", headers=data["headers"], params={
            "q": data["prefix"], "page": page, "page_size": 2,
        })
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["total"] == 3
        assert body["page"] == page
        assert body["page_size"] == 2
        assert [item["id"] for item in body["items"]] == ids
    detail = test_client.get(f"/api/v1/classes/{expected[0]}", headers=data["headers"])
    assert detail.status_code == 200


def test_student_class_search_and_filters_keep_membership_scope(
    test_client, base_data, paginated_classes,
):
    data = paginated_classes
    for index, expected in [(12, 1), (0, 0), (15, 0), (16, 0)]:
        response = test_client.get("/api/v1/classes", headers=data["headers"], params={
            "q": data["rows"][index].code, "semester_id": base_data["sem"].id,
            "subject_id": base_data["sub"].id, "lecturer_id": base_data["lec"].id,
            "status": "active", "page_size": 1,
        })
        assert response.status_code == 200
        assert response.json()["total"] == expected
        assert len(response.json()["items"]) == expected


def test_student_cannot_select_another_student_via_query(
    test_client, db_session, base_data, paginated_classes,
):
    data = paginated_classes
    # This account has the student role but no Student profile or enrollments.
    user = User(
        username=f"f01_empty_{_uid()}", email=f"{_uid()}@test.local",
        password_hash=base_data["user_stu"].password_hash, role=UserRole.student,
        is_active=True, must_change_password=False, is_deleted=False, token_version=1,
    )
    db_session.add(user)
    db_session.commit()
    response = test_client.get("/api/v1/classes", headers={
        "Authorization": f"Bearer {_make_token(user)}",
    }, params={"q": data["prefix"], "student_id": base_data["stu"].id})
    assert response.status_code == 200
    assert response.json()["total"] == 0
    assert response.json()["items"] == []


@pytest.mark.parametrize("deleted", [False, True])
def test_student_without_active_profile_or_enrollment_sees_no_classes(
    test_client, db_session, base_data, paginated_classes, deleted,
):
    data = paginated_classes
    if deleted:
        base_data["stu"].is_deleted = True
    else:
        for row in db_session.query(ClassStudent).filter(
            ClassStudent.student_id == base_data["stu"].id,
        ):
            row.status = ClassStudentStatus.dropped
    db_session.commit()
    response = test_client.get("/api/v1/classes", headers=data["headers"], params={"q": data["prefix"]})
    assert response.status_code == 200
    assert response.json()["total"] == 0
    assert response.json()["items"] == []


def test_class_list_admin_and_lecturer_scopes(test_client, db_session, base_data, paginated_classes):
    data = paginated_classes
    for headers, expected in [
        (_admin_headers(db_session), 16),
        ({"Authorization": f"Bearer {_make_token(base_data['user_lec'])}"}, 16),
        ({"Authorization": f"Bearer {_make_token(base_data['user_lec2'])}"}, 0),
    ]:
        response = test_client.get("/api/v1/classes", headers=headers, params={
            "q": data["prefix"], "page_size": 2,
        })
        assert response.status_code == 200
        assert response.json()["total"] == expected
        assert len(response.json()["items"]) == min(expected, 2)
    response = test_client.get("/api/v1/classes", headers={
        "Authorization": f"Bearer {_make_token(base_data['user_lec2'])}",
    }, params={"q": data["prefix"], "lecturer_id": base_data["lec"].id})
    assert response.json()["total"] == 0


@pytest.mark.parametrize("params", [
    {"page": 0}, {"page": -1}, {"page_size": 0}, {"page_size": 101}, {"page": "abc"},
])
def test_class_list_rejects_invalid_pagination(test_client, base_data, params):
    response = test_client.get("/api/v1/classes", params=params, headers={
        "Authorization": f"Bearer {_make_token(base_data['user_stu'])}",
    })
    assert response.status_code == 422


def test_class_list_requires_authentication(test_client):
    assert test_client.get("/api/v1/classes").status_code == 401


def test_class_service_scopes_direct_calls(db_session, base_data, paginated_classes):
    from app.services.class_service import get_classes_paginated

    items, total = get_classes_paginated(
        db_session, actor=base_data["user_stu"], page_size=1,
        q=paginated_classes["prefix"],
    )
    assert total == 3
    assert [item.id for item in items] == [paginated_classes["rows"][12].id]
