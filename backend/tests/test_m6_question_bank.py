from io import BytesIO
from uuid import uuid4

from openpyxl import load_workbook

from app.models.audit import AuditLog
from app.models.class_ import Class, ClassStatus
from app.models.lecturer import Lecturer, LecturerType
from app.models.user import User, UserRole
from app.services.question_import_service import template
from tests.test_m4_m5 import _admin, _learning_data, _token


def _second_lecturer(db, cls):
    suffix = uuid4().hex[:10]
    user = User(username=f"m6l{suffix}", email=f"m6l{suffix}@test.local", password_hash="unused",
        role=UserRole.lecturer, is_active=True, is_deleted=False, must_change_password=False, token_version=1)
    db.add(user)
    db.flush()
    lecturer = Lecturer(user_id=user.id, code=f"m6{suffix}", full_name="Giảng viên M6",
        type=LecturerType.full_time, is_deleted=False)
    db.add(lecturer)
    db.flush()
    db.add(Class(code=f"m6c{suffix}", subject_id=cls.subject_id, semester_id=cls.semester_id,
        lecturer_id=lecturer.id, status=ClassStatus.active, is_deleted=False))
    db.commit()
    return user


def _payload(kind="single"):
    return {"type": kind, "content": "Câu hỏi mẫu", "difficulty": "medium", "explanation": None,
        "options": [{"content": "A", "is_correct": True}, {"content": "B", "is_correct": False}]}


def test_question_bank_permissions_and_crud(test_client, db_session):
    cls, lecturer, student = _learning_data(db_session)
    other = _second_lecturer(db_session, cls)
    admin = _admin(db_session, uuid4().hex[:8])
    base = f"/api/v1/subjects/{cls.subject_id}/questions"
    created = test_client.post(base, headers=_token(lecturer), json=_payload())
    assert created.status_code == 201, created.text
    question_id = created.json()["id"]
    response = test_client.get(base, headers=_token(other))
    assert response.status_code == 200
    assert response.json()["items"][0]["can_edit"] is False
    assert test_client.put(f"/api/v1/questions/{question_id}", headers=_token(other), json=_payload()).status_code == 403
    assert test_client.delete(f"/api/v1/questions/{question_id}", headers=_token(other)).status_code == 403
    assert test_client.get(base, headers=_token(student)).status_code == 403
    assert test_client.get(f"/api/v1/questions/{question_id}", headers=_token(student)).status_code == 403
    updated = _payload("multiple")
    updated["options"][1]["is_correct"] = True
    assert test_client.put(f"/api/v1/questions/{question_id}", headers=_token(lecturer), json=updated).status_code == 200
    assert test_client.get(base, headers=_token(other), params={"question_type": "multiple"}).json()["total"] == 1
    assert test_client.delete(f"/api/v1/questions/{question_id}", headers=_token(admin)).status_code == 204
    actions = {row.action for row in db_session.query(AuditLog).filter(
        AuditLog.entity == "questions", AuditLog.entity_id == str(question_id)).all()}
    assert {"CREATE_QUESTION", "UPDATE_QUESTION", "DELETE_QUESTION"}.issubset(actions)


def test_question_validation_and_closed_class(test_client, db_session):
    cls, lecturer, _ = _learning_data(db_session)
    base = f"/api/v1/subjects/{cls.subject_id}/questions"
    payload = _payload()
    payload["options"][0]["is_correct"] = False
    assert test_client.post(base, headers=_token(lecturer), json=payload).status_code == 422
    payload = _payload("essay")
    assert test_client.post(base, headers=_token(lecturer), json=payload).status_code == 422
    invalid_tf = _payload("true_false")
    invalid_tf["options"].append({"content": "Không chắc", "is_correct": False})
    assert test_client.post(base, headers=_token(lecturer), json=invalid_tf).status_code == 422
    payload["options"] = []
    assert test_client.post(base, headers=_token(lecturer), json=payload).status_code == 201
    db_session.refresh(cls)
    cls.status = ClassStatus.closed
    db_session.commit()
    assert test_client.get(base, headers=_token(lecturer)).status_code == 403


def test_excel_preview_and_confirm_revalidate(test_client, db_session):
    cls, lecturer, student = _learning_data(db_session)
    base = f"/api/v1/subjects/{cls.subject_id}/questions/import"
    workbook = load_workbook(BytesIO(template()))
    sheet = workbook.active
    sheet.append(["single", "Câu hợp lệ", "easy", "", "Có", "Không", "", "", "", "", "A"])
    sheet.append(["single", "Thiếu đáp án đúng", "easy", "", "A", "B", "", "", "", "", ""])
    sheet.append(["essay", "=1+1", "easy", "", "", "", "", "", "", "", ""])
    file = BytesIO()
    workbook.save(file)
    files = {"file": ("questions.xlsx", file.getvalue(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
    assert test_client.post(f"{base}/preview", files=files, headers=_token(student)).status_code == 403
    response = test_client.post(f"{base}/preview", files=files, headers=_token(lecturer))
    assert response.status_code == 200, response.text
    data = response.json()
    assert len(data["valid"]) == 1
    assert [row["row"] for row in data["errors"]] == [3, 4]
    invalid = _payload()
    invalid["options"][0]["is_correct"] = False
    assert test_client.post(f"{base}/confirm", headers=_token(lecturer), json={"items": [data["valid"][0]["item"], invalid]}).status_code == 422
    assert test_client.get(f"/api/v1/subjects/{cls.subject_id}/questions", headers=_token(lecturer)).json()["total"] == 0
    confirmed = test_client.post(f"{base}/confirm", headers=_token(lecturer), json={"items": [data["valid"][0]["item"]]})
    assert confirmed.status_code == 201
    assert confirmed.json()["created"] == 1
