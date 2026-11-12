import io
import logging
from pathlib import Path
from uuid import uuid4

import openpyxl
import pytest
from sqlalchemy.exc import IntegrityError

from app.core.security import create_access_token, get_password_hash, verify_password
from app.models.audit import AuditLog
from app.models.department import Department
from app.models.student import Student
from app.models.user import User, UserRole
from app.services import student_service


@pytest.fixture
def import_departments(db_session):
    departments = []
    for code, active in (("TESTIMP", True), ("TESTOFF", False)):
        department = db_session.query(Department).filter_by(code=code).first()
        if department is None:
            department = Department(code=code, name=f"Khoa kiểm thử {code}", is_active=active)
            db_session.add(department)
        departments.append(department)
    db_session.commit()
    return departments


def workbook_bytes(rows):
    workbook = openpyxl.Workbook()
    for row in rows:
        workbook.active.append(row)
    output = io.BytesIO()
    workbook.save(output)
    return output.getvalue()


def preview(test_client, admin_headers, content):
    return test_client.post(
        "/api/v1/students/import/preview",
        files={"file": ("students.xlsx", content, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        headers=admin_headers,
    )


def test_import_preview_mixed(test_client, admin_headers, import_departments):
    file_path = Path(__file__).resolve().parent / "fixtures" / "students_mixed.xlsx"
    workbook = openpyxl.load_workbook(file_path)
    sheet = workbook.active
    column = sheet.max_column + 1
    sheet.cell(1, column, "Mã khoa (*)")
    for row in range(2, sheet.max_row + 1):
        sheet.cell(row, column, "TESTIMP")
    content = io.BytesIO()
    workbook.save(content)
    resp = preview(test_client, admin_headers, content.getvalue())

    assert resp.status_code == 200
    data = resp.json()
    assert data["valid_count"] == len(data["valid_rows"])
    assert data["warning_count"] == len(data["warning_rows"])
    assert data["error_count"] == len(data["error_rows"])
    assert data["valid_count"] >= 1
    assert data["error_count"] >= 1


def test_import_confirm_creates_records(test_client, admin_headers, db_session, import_departments):
    valid_rows = [{
        "row": 2,
        "student_code": "SVIMPORT991",
        "full_name": "Sinh Vien Import Test 991",
        "admin_class": "K65-CNTT",
        "email": "svimport991@lmstest.edu.vn",
        "department_code": " testimp ",
        "department_name": "Tên giả không được tin",
        "department_id": 999999,
    }]
    resp = test_client.post("/api/v1/students/import/confirm", json={"valid_rows": valid_rows}, headers=admin_headers)
    assert resp.status_code == 200
    assert "spreadsheetml" in resp.headers.get("content-type", "")
    db_session.rollback()
    new_st = db_session.query(Student).filter_by(student_code="SVIMPORT991").first()
    assert new_st is not None
    assert new_st.department_id == import_departments[0].id
    new_user = db_session.query(User).filter_by(username="svimport991").first()
    assert new_user is not None
    assert new_user.must_change_password is True
    sheet = openpyxl.load_workbook(io.BytesIO(resp.content)).active
    assert sheet.max_row == 2
    assert sheet.cell(2, 1).value == "SVIMPORT991"
    assert verify_password(sheet.cell(2, 4).value, new_user.password_hash)
    audit = db_session.query(AuditLog).filter_by(action="IMPORT_STUDENTS").order_by(AuditLog.id.desc()).first()
    assert "temp_password" not in str(audit.detail)
    assert new_user.password_hash not in str(audit.detail)


def test_preview_department_errors_and_column_names(test_client, admin_headers, import_departments):
    content = workbook_bytes([
        ["MSSV", "Họ và tên", "Tên khoa", "Mã khoa (*)"],
        ["SVIMPA", "Tên thật", "Tên không được thay họ tên", " testimp "],
        ["SVIMPB", "Thiếu khoa", "", ""],
        ["SVIMPC", "Không tồn tại", "", "UNKNOWN"],
        ["SVIMPD", "Ngừng hoạt động", "", "TESTOFF"],
    ])
    response = preview(test_client, admin_headers, content)
    assert response.status_code == 200
    result = response.json()
    assert result["total_rows"] == 4
    assert result["valid_count"] == 1
    assert result["valid_rows"][0]["full_name"] == "Tên thật"
    assert result["valid_rows"][0]["department_code"] == "TESTIMP"
    assert result["valid_rows"][0]["department_name"] == "Khoa kiểm thử TESTIMP"
    assert result["error_count"] == 3
    reasons = " ".join(row["reason"] for row in result["error_rows"])
    assert "Thiếu mã khoa" in reasons
    assert "không tồn tại" in reasons
    assert "ngừng sử dụng" in reasons


def test_preview_old_template_requires_department(test_client, admin_headers, import_departments):
    content = workbook_bytes([["MSSV", "Họ và tên", "Lớp hành chính"], ["SVIMPOLD", "Tên SV", "CNTT"]])
    result = preview(test_client, admin_headers, content).json()
    assert result["valid_count"] == 0
    assert "Thiếu mã khoa" in result["error_rows"][0]["reason"]


def test_template_includes_required_department_column(test_client, admin_headers):
    response = test_client.get("/api/v1/students/import/template", headers=admin_headers)
    assert response.status_code == 200
    sheet = openpyxl.load_workbook(io.BytesIO(response.content)).active
    assert "Mã khoa (*)" in [cell.value for cell in sheet[1]]


def test_department_deactivated_after_preview_is_rejected(test_client, admin_headers, db_session, import_departments):
    content = workbook_bytes([["MSSV", "Họ và tên", "Mã khoa"], ["SVIMPSTALE", "Tên SV", "TESTIMP"]])
    result = preview(test_client, admin_headers, content).json()
    assert result["valid_count"] == 1
    department = import_departments[0]
    department.is_active = False
    db_session.commit()
    try:
        response = test_client.post("/api/v1/students/import/confirm", json={"valid_rows": result["valid_rows"]}, headers=admin_headers)
        assert response.status_code == 422
        assert "ngừng sử dụng" in response.json()["detail"]["message"]
        db_session.rollback()
        assert db_session.query(Student).filter_by(student_code="SVIMPSTALE").first() is None
    finally:
        department.is_active = True
        db_session.commit()


@pytest.mark.parametrize("department_code", [None, "UNKNOWN", "TESTOFF"])
def test_confirm_rejects_invalid_department_without_partial_creation(
    test_client, admin_headers, db_session, import_departments, department_code
):
    rows = [
        {"row": 2, "student_code": "SVIMPPARTIAL", "full_name": "Đúng", "department_code": "TESTIMP"},
        {"row": 3, "student_code": "SVIMPINVALID", "full_name": "Sai", "department_code": department_code},
    ]
    response = test_client.post("/api/v1/students/import/confirm", json={"valid_rows": rows}, headers=admin_headers)
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "INVALID_DEPARTMENT"
    db_session.rollback()
    assert db_session.query(Student).filter_by(student_code="SVIMPPARTIAL").first() is None
    assert db_session.query(User).filter_by(username="svimppartial").first() is None


def test_existing_student_is_skipped_without_modification(test_client, admin_headers, db_session, import_departments):
    user = User(username="svimpexisting", email="svimpexisting@test.local", password_hash=get_password_hash("Test@12345"),
                role=UserRole.student, is_active=True, must_change_password=False, is_deleted=False)
    db_session.add(user)
    db_session.flush()
    student = Student(user_id=user.id, student_code="SVIMPEXISTING", full_name="Tên ban đầu", department_id=None)
    db_session.add(student)
    db_session.commit()
    old_hash = user.password_hash
    row = {"row": 2, "student_code": "SVIMPEXISTING", "full_name": "Tên mới", "department_code": "TESTIMP"}
    result = preview(test_client, admin_headers, workbook_bytes([
        ["MSSV", "Họ và tên", "Mã khoa"], ["SVIMPEXISTING", "Tên mới", "TESTIMP"],
    ])).json()
    assert result["valid_count"] == 0
    assert "đã tồn tại" in result["warning_rows"][0]["reason"]
    response = test_client.post("/api/v1/students/import/confirm", json={"valid_rows": [row]}, headers=admin_headers)
    assert response.status_code == 200
    db_session.expire_all()
    assert student.full_name == "Tên ban đầu"
    assert student.department_id is None
    assert user.password_hash == old_hash


def test_import_is_admin_only(test_client, db_session):
    user = User(username="import_role_test", email="import_role_test@test.local", password_hash=get_password_hash("Test@12345"),
                role=UserRole.student, is_active=True, must_change_password=False, is_deleted=False, token_version=1)
    db_session.add(user)
    db_session.commit()
    token = create_access_token({"sub": str(user.id), "role": user.role.value, "token_version": 1})
    headers = {"Authorization": f"Bearer {token}"}
    assert preview(test_client, headers, workbook_bytes([["MSSV", "Họ và tên"], ["X", "Y"]])).status_code == 403
    assert test_client.post("/api/v1/students/import/confirm", json={"valid_rows": []}, headers=headers).status_code == 403


def test_preview_skips_soft_deleted_student(test_client, admin_headers, db_session, import_departments):
    user = User(username="svimpdeleted", email="svimpdeleted@test.local", password_hash=get_password_hash("Test@12345"),
                role=UserRole.student, is_active=False, is_deleted=True)
    db_session.add(user)
    db_session.flush()
    db_session.add(Student(user_id=user.id, student_code="SVIMPDELETED", full_name="Đã xóa", is_deleted=True))
    db_session.commit()
    result = preview(test_client, admin_headers, workbook_bytes([
        ["MSSV", "Họ và tên", "Mã khoa"], ["SVIMPDELETED", "Tên mới", "TESTIMP"],
    ])).json()
    assert result["valid_count"] == 0
    assert "đã tồn tại" in result["warning_rows"][0]["reason"]


def _f05_row(code, row=2):
    return {"row": row, "student_code": code, "full_name": "Sinh viên F05", "department_code": "TESTIMP"}


def _f05_account(db, code, deleted=False):
    user = User(username=code.lower(), email=f"{code.lower()}@test.local",
                password_hash=get_password_hash("Test@12345"), role=UserRole.lecturer,
                is_active=not deleted, is_deleted=deleted, must_change_password=False)
    db.add(user)
    db.commit()
    return user


@pytest.mark.parametrize("deleted", [False, True])
def test_f05_username_conflict_has_row_error_and_preserves_account(
    test_client, admin_headers, db_session, import_departments, deleted
):
    code = f"F05{uuid4().hex[:12]}"
    owner = _f05_account(db_session, code, deleted)
    old_hash = owner.password_hash
    content = workbook_bytes([["MSSV", "Họ và tên", "Mã khoa"], [code, "Tên SV", "TESTIMP"]])
    result = preview(test_client, admin_headers, content).json()
    assert result["valid_count"] == 0
    assert result["error_rows"][0]["row"] == 2
    assert "tên đăng nhập" in result["error_rows"][0]["reason"].lower()
    response = test_client.post("/api/v1/students/import/confirm",
        json={"valid_rows": [_f05_row(code)]}, headers=admin_headers)
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "IMPORT_USERNAME_CONFLICT"
    assert response.json()["detail"]["details"]["rows"][0]["row"] == 2
    assert old_hash not in response.text
    assert "INSERT INTO" not in response.text
    db_session.expire_all()
    assert owner.password_hash == old_hash
    assert owner.role == UserRole.lecturer
    assert owner.is_deleted == deleted
    assert db_session.query(Student).filter_by(student_code=code).first() is None


def test_f05_conflict_created_after_preview_rolls_back_whole_batch(
    test_client, admin_headers, db_session, import_departments
):
    good, conflict = f"F05{uuid4().hex[:12]}", f"F05{uuid4().hex[:12]}"
    content = workbook_bytes([["MSSV", "Họ và tên", "Mã khoa"],
                              [good, "Đúng", "TESTIMP"], [conflict, "Xung đột", "TESTIMP"]])
    result = preview(test_client, admin_headers, content).json()
    assert result["valid_count"] == 2
    _f05_account(db_session, conflict)
    audit_count = db_session.query(AuditLog).filter_by(action="IMPORT_STUDENTS").count()
    response = test_client.post("/api/v1/students/import/confirm",
        json={"valid_rows": result["valid_rows"]}, headers=admin_headers)
    assert response.status_code == 409
    assert response.json()["detail"]["details"]["rows"][0]["row"] == 3
    db_session.expire_all()
    assert db_session.query(User).filter_by(username=good.lower()).first() is None
    assert db_session.query(Student).filter(Student.student_code.in_([good, conflict])).count() == 0
    assert db_session.query(AuditLog).filter_by(action="IMPORT_STUDENTS").count() == audit_count


@pytest.mark.parametrize("failure_kind", ["integrity", "unexpected", "workbook"])
def test_f05_failure_is_sanitized_and_atomic(
    test_client, admin_headers, db_session, import_departments, monkeypatch, caplog, failure_kind
):
    code = f"F05{uuid4().hex[:12]}"
    secret = "F05_SECRET_PARAMETER_SENTINEL"
    internal = f"INSERT INTO users (password_hash) VALUES ({secret}); C:/private/database"
    original_log = student_service.log_action
    original_workbook = student_service.generate_student_import_result_excel

    def fail(*args, **kwargs):
        if failure_kind == "integrity":
            raise IntegrityError("INSERT INTO users (password_hash)", {"password_hash": secret}, Exception(internal))
        raise RuntimeError(internal)

    if failure_kind == "workbook":
        monkeypatch.setattr(student_service, "generate_student_import_result_excel", fail)
    else:
        def fail_after_audit(*args, **kwargs):
            original_log(*args, **kwargs)
            fail()
        monkeypatch.setattr(student_service, "log_action", fail_after_audit)
    audit_count = db_session.query(AuditLog).filter_by(action="IMPORT_STUDENTS").count()
    with caplog.at_level(logging.WARNING, logger="app.services.student_service"):
        response = test_client.post("/api/v1/students/import/confirm",
            json={"valid_rows": [_f05_row(code)]}, headers=admin_headers)
    assert response.status_code == (409 if failure_kind == "integrity" else 500)
    detail = response.json()["detail"]
    assert detail["code"] == ("IMPORT_CONFLICT" if failure_kind == "integrity" else "IMPORT_FAILED")
    assert secret not in response.text + caplog.text
    assert "INSERT INTO" not in response.text + caplog.text
    assert "C:/private" not in response.text + caplog.text
    if failure_kind != "integrity":
        reference = detail["details"]["reference"]
        assert len(reference) == 32
        assert reference in caplog.text
    db_session.expire_all()
    assert db_session.query(User).filter_by(username=code.lower()).first() is None
    assert db_session.query(Student).filter_by(student_code=code).first() is None
    assert db_session.query(AuditLog).filter_by(action="IMPORT_STUDENTS").count() == audit_count

    monkeypatch.setattr(student_service, "log_action", original_log)
    monkeypatch.setattr(student_service, "generate_student_import_result_excel", original_workbook)
    retry = test_client.post("/api/v1/students/import/confirm",
        json={"valid_rows": [_f05_row(code)]}, headers=admin_headers)
    assert retry.status_code == 200
    db_session.expire_all()
    assert db_session.query(Student).filter_by(student_code=code).count() == 1


def test_f05_confirm_requires_authentication(test_client):
    assert test_client.post("/api/v1/students/import/confirm", json={"valid_rows": []}).status_code == 401
