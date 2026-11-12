"""Regression và negative tests tối thiểu cho M4/M5."""

from datetime import date, datetime, time, timedelta
from pathlib import Path

from app.core.config import settings
from app.core.security import create_access_token, get_password_hash
from app.models.attendance import AttendanceRecord, AttendanceSource, AttendanceStatus
from app.models.class_ import Class, ClassStatus, ClassStudent, ClassStudentStatus
from app.models.learning import FaceConsent, FaceTemplate, Notification
from app.models.lecturer import Lecturer, LecturerType
from app.models.semester import Semester
from app.models.session import Session as SessionModel
from app.models.session import SessionStatus
from app.models.student import Student, StudentStatus
from app.models.subject import Subject
from app.models.user import User, UserRole
from app.services import attendance_service
from app.utils.clock import VN_TZ, now_local, override_clock


def _token(user: User) -> dict:
    return {
        "Authorization": f"Bearer {create_access_token({'sub': str(user.id), 'role': user.role.value, 'token_version': user.token_version})}"
    }


def _learning_data(db):
    suffix = str(int(datetime.now().timestamp() * 1_000_000))[-8:]
    lecturer_user = User(
        username=f"m5lec{suffix}",
        email=f"m5lec{suffix}@test.local",
        password_hash=get_password_hash("Demo@123"),
        role=UserRole.lecturer,
        is_active=True,
        must_change_password=False,
        is_deleted=False,
        token_version=1,
    )
    student_user = User(
        username=f"m5stu{suffix}",
        email=f"m5stu{suffix}@test.local",
        password_hash=get_password_hash("Demo@123"),
        role=UserRole.student,
        is_active=True,
        must_change_password=False,
        is_deleted=False,
        token_version=1,
    )
    db.add_all([lecturer_user, student_user])
    db.flush()
    lecturer = Lecturer(
        user_id=lecturer_user.id,
        code=f"M5L{suffix}",
        full_name="GV M5",
        type=LecturerType.full_time,
        is_deleted=False,
    )
    student = Student(
        user_id=student_user.id,
        student_code=f"M5S{suffix}",
        full_name="SV M5",
        status=StudentStatus.studying,
        is_deleted=False,
    )
    semester = Semester(
        name=f"M5 {suffix}",
        start_date=datetime.now().date(),
        end_date=(datetime.now() + timedelta(days=90)).date(),
    )
    subject = Subject(code=f"M5{suffix}", name="Môn M5", credits=3)
    db.add_all([lecturer, student, semester, subject])
    db.flush()
    cls = Class(
        code=f"M5C{suffix}",
        subject_id=subject.id,
        semester_id=semester.id,
        lecturer_id=lecturer.id,
        status=ClassStatus.active,
        is_deleted=False,
    )
    db.add(cls)
    db.flush()
    db.add(ClassStudent(class_id=cls.id, student_id=student.id, status=ClassStudentStatus.enrolled))
    db.commit()
    return cls, lecturer_user, student_user


def _admin(db, suffix: str) -> User:
    user = User(
        username=f"m5admin{suffix}",
        email=f"m5admin{suffix}@test.local",
        password_hash=get_password_hash("Demo@123"),
        role=UserRole.admin,
        is_active=True,
        must_change_password=False,
        is_deleted=False,
        token_version=1,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _second_student(db, cls: Class, suffix: str = "second") -> tuple[Student, User]:
    unique = str(int(datetime.now().timestamp() * 1_000_000))[-8:]
    user = User(
        username=f"{suffix}{unique}",
        email=f"{suffix}{unique}@test.local",
        password_hash=get_password_hash("Demo@123"),
        role=UserRole.student,
        is_active=True,
        must_change_password=False,
        is_deleted=False,
        token_version=1,
    )
    db.add(user)
    db.flush()
    student = Student(
        user_id=user.id,
        student_code=f"S{unique}",
        full_name="Sinh viên thứ hai",
        status=StudentStatus.studying,
        is_deleted=False,
    )
    db.add(student)
    db.flush()
    db.add(
        ClassStudent(
            class_id=cls.id, student_id=student.id, status=ClassStudentStatus.enrolled
        )
    )
    db.commit()
    return student, user


def test_face_mock_and_consent_flow(test_client, db_session):
    _, lecturer_user, student_user = _learning_data(db_session)
    assert (
        test_client.get("/api/v1/face/status", headers=_token(lecturer_user)).json()["is_ready"]
        is False
    )
    assert (
        test_client.post(
            "/api/v1/students/me/face/consent",
            json={"text_version": "v1"},
            headers=_token(student_user),
        ).status_code
        == 200
    )
    profile = test_client.get("/api/v1/students/me/face", headers=_token(student_user)).json()
    assert profile["consented"] is True
    assert (
        test_client.post("/api/v1/admin/face/reindex", headers=_token(lecturer_user)).status_code
        == 403
    )
    assert (
        test_client.delete(
            "/api/v1/students/me/face/consent", headers=_token(student_user)
        ).status_code
        == 200
    )


def test_assignment_submission_and_role_boundary(test_client, db_session):
    cls, lecturer_user, student_user = _learning_data(db_session)
    payload = {
        "title": "Bài M5",
        "description": "Nội dung",
        "due_at": (now_local() + timedelta(hours=1)).isoformat(),
        "max_score": 10,
        "allow_late": False,
        "status": "published",
    }
    assignment = test_client.post(
        f"/api/v1/classes/{cls.id}/assignments", json=payload, headers=_token(lecturer_user)
    )
    assert assignment.status_code == 200, assignment.text
    assignment_id = assignment.json()["id"]
    assert (
        test_client.post(
            f"/api/v1/assignments/{assignment_id}/submissions",
            json={"text": "Bài làm"},
            headers=_token(student_user),
        ).status_code
        == 200
    )
    assert (
        test_client.get(
            f"/api/v1/assignments/{assignment_id}/submissions", headers=_token(student_user)
        ).status_code
        == 403
    )
    assert (
        test_client.get("/api/v1/notifications", headers=_token(student_user)).json()[
            "unread_count"
        ]
        >= 1
    )


def test_face_enrollment_validates_content_and_revoke_deletes_file(
    test_client, db_session, tmp_path, monkeypatch
):
    _, _, student_user = _learning_data(db_session)
    monkeypatch.setattr(settings, "FACE_STORAGE_DIR", str(tmp_path / "face"))

    missing_consent = test_client.post(
        "/api/v1/students/me/face/enroll",
        files={"images": ("face.jpg", b"\xff\xd8\xffpayload", "image/jpeg")},
        headers=_token(student_user),
    )
    assert missing_consent.status_code == 409
    assert missing_consent.json()["detail"]["code"] == "FACE_CONSENT_REQUIRED"

    test_client.post(
        "/api/v1/students/me/face/consent",
        json={"text_version": "v1.0"},
        headers=_token(student_user),
    )
    invalid = test_client.post(
        "/api/v1/students/me/face/enroll",
        files={"images": ("fake.jpg", b"not-an-image", "image/jpeg")},
        headers=_token(student_user),
    )
    assert invalid.status_code == 200
    assert invalid.json()["accepted"] == 0
    assert invalid.json()["items"][0]["reason"] == "invalid_image"

    enrolled = test_client.post(
        "/api/v1/students/me/face/enroll",
        files={"images": ("face.jpg", b"\xff\xd8\xffpayload", "image/jpeg")},
        headers=_token(student_user),
    )
    assert enrolled.status_code == 200
    assert enrolled.json()["accepted"] == 1
    template = db_session.query(FaceTemplate).order_by(FaceTemplate.id.desc()).first()
    assert template is not None
    stored_path = Path(template.image_path)
    assert stored_path.is_file()

    revoked = test_client.delete(
        "/api/v1/students/me/face/consent", headers=_token(student_user)
    )
    assert revoked.status_code == 200
    assert revoked.json()["consented"] is False
    assert not stored_path.exists()
    db_session.expire_all()
    assert db_session.get(FaceTemplate, template.id).embedding is None


def test_face_revoke_does_not_claim_success_when_file_delete_fails(
    test_client, db_session, tmp_path, monkeypatch
):
    _, _, student_user = _learning_data(db_session)
    monkeypatch.setattr(settings, "FACE_STORAGE_DIR", str(tmp_path / "face"))
    test_client.post(
        "/api/v1/students/me/face/consent",
        json={"text_version": "v1.0"},
        headers=_token(student_user),
    )
    test_client.post(
        "/api/v1/students/me/face/enroll",
        files={"images": ("face.png", b"\x89PNG\r\n\x1a\npayload", "image/png")},
        headers=_token(student_user),
    )

    original_unlink = Path.unlink

    def fail_face_unlink(path: Path, *args, **kwargs):
        if str(tmp_path) in str(path):
            raise PermissionError("locked")
        return original_unlink(path, *args, **kwargs)

    monkeypatch.setattr(Path, "unlink", fail_face_unlink)
    response = test_client.delete(
        "/api/v1/students/me/face/consent", headers=_token(student_user)
    )
    assert response.status_code == 500
    assert response.json()["detail"]["code"] == "FACE_DATA_DELETE_FAILED"
    db_session.expire_all()
    assert (
        db_session.query(FaceConsent)
        .filter(FaceConsent.student.has(user_id=student_user.id), FaceConsent.revoked_at.is_(None))
        .count()
        == 0
    )
    assert test_client.get("/api/v1/students/me/face", headers=_token(student_user)).json()["cleanup_pending"] is True
    assert db_session.query(FaceTemplate).filter(FaceTemplate.student.has(user_id=student_user.id),
                                                FaceTemplate.embedding.is_not(None)).count() == 0


def test_face_mock_recognize_and_reindex_contract(test_client, db_session):
    cls, lecturer_user, student_user = _learning_data(db_session)
    admin = _admin(db_session, str(cls.id))
    session = SessionModel(
        class_id=cls.id,
        session_no=1,
        date=date(2026, 10, 18),
        start_time=time(8, 0),
        end_time=time(10, 0),
        room="A101",
        status=SessionStatus.open,
    )
    db_session.add(session)
    db_session.commit()

    result = test_client.post(
        f"/api/v1/sessions/{session.id}/recognize",
        files={"frame": ("frame.jpg", b"\xff\xd8\xffframe", "image/jpeg")},
        headers=_token(lecturer_user),
    )
    assert result.status_code == 200
    assert result.json() == {
        "engine": "mock",
        "ready": False,
        "faces": [],
        "attendance_changes": [],
    }
    assert (
        test_client.post("/api/v1/admin/face/reindex", headers=_token(admin)).status_code == 409
    )
    assert test_client.get("/api/v1/face/status", headers=_token(student_user)).status_code == 403


def test_face_match_requires_consecutive_valid_hits(db_session, monkeypatch):
    cls, _, student_user = _learning_data(db_session)
    student = db_session.query(Student).filter(Student.user_id == student_user.id).one()
    session = SessionModel(
        class_id=cls.id,
        session_no=2,
        date=date(2026, 10, 18),
        start_time=time(8, 0),
        end_time=time(10, 0),
        room="A102",
        status=SessionStatus.open,
    )
    db_session.add(session)
    db_session.flush()
    record = AttendanceRecord(
        session_id=session.id,
        student_id=student.id,
        status=AttendanceStatus.absent,
        source=AttendanceSource.system,
    )
    db_session.add(record)
    db_session.commit()
    monkeypatch.setattr(settings, "FACE_MIN_HITS", 2)
    monkeypatch.setattr(settings, "FACE_MATCH_THRESHOLD", 0.7)
    monkeypatch.setattr(settings, "FACE_MARGIN_THRESHOLD", 0.1)

    with override_clock(datetime(2026, 10, 18, 8, 5, tzinfo=VN_TZ)):
        _, result = attendance_service.apply_face_match(db_session, session, student.id, 0.9, 0.2)
        assert result == "pending_hits"
        assert record.hit_count == 1
        _, result = attendance_service.apply_face_match(db_session, session, student.id, 0.5, 0.2)
        assert result == "below_threshold"
        assert record.hit_count == 0
        attendance_service.apply_face_match(db_session, session, student.id, 0.9, 0.2)
        _, result = attendance_service.apply_face_match(db_session, session, student.id, 0.9, 0.2)

    assert result == "present"
    assert record.status == AttendanceStatus.present
    assert record.hit_count == 2


def test_assignment_late_resubmit_grade_and_file_acl(
    test_client, db_session, tmp_path, monkeypatch
):
    cls, lecturer_user, student_user = _learning_data(db_session)
    _, other_user = _second_student(db_session, cls)
    monkeypatch.setattr(settings, "UPLOAD_STORAGE_DIR", str(tmp_path / "uploads"))
    fixed = datetime(2026, 10, 18, 9, 0, tzinfo=VN_TZ)

    with override_clock(fixed):
        assignment = test_client.post(
            f"/api/v1/classes/{cls.id}/assignments",
            json={
                "title": "Bài có tệp",
                "description": "Nộp PDF",
                "due_at": (fixed + timedelta(hours=1)).isoformat(),
                "max_score": 10,
                "allow_late": False,
                "status": "published",
            },
            headers=_token(lecturer_user),
        ).json()
        submitted = test_client.post(
            f"/api/v1/assignments/{assignment['id']}/submissions/file",
            files={"file": ("answer.pdf", b"%PDF-1.4\nanswer", "application/pdf")},
            headers=_token(student_user),
        )
        assert submitted.status_code == 200
        submission_id = submitted.json()["id"]
        assert submitted.json()["has_file"] is True
        assert (
            test_client.get(
                f"/api/v1/submissions/{submission_id}/file", headers=_token(other_user)
            ).status_code
            == 403
        )
        assert (
            test_client.get(
                f"/api/v1/submissions/{submission_id}/file", headers=_token(lecturer_user)
            ).status_code
            == 200
        )
        graded = test_client.post(
            f"/api/v1/submissions/{submission_id}/grade",
            json={"score": 8.5, "feedback": "Đạt"},
            headers=_token(lecturer_user),
        )
        assert graded.status_code == 200
        assert (
            test_client.post(
                f"/api/v1/submissions/{submission_id}/grade",
                json={"score": 11},
                headers=_token(lecturer_user),
            ).status_code
            == 422
        )
        resubmitted = test_client.post(
            f"/api/v1/assignments/{assignment['id']}/submissions",
            json={"text": "Bản nộp lại"},
            headers=_token(student_user),
        )
        assert resubmitted.status_code == 200
        assert resubmitted.json()["score"] is None
        assert resubmitted.json()["has_file"] is False

    with override_clock(fixed + timedelta(hours=2)):
        late = test_client.post(
            f"/api/v1/assignments/{assignment['id']}/submissions",
            json={"text": "Quá hạn"},
            headers=_token(student_user),
        )
        assert late.status_code == 409
        assert late.json()["detail"]["code"] == "ASSIGNMENT_CLOSED"


def test_groups_announcements_and_notification_isolation(test_client, db_session):
    cls, lecturer_user, student_user = _learning_data(db_session)
    second_student, second_user = _second_student(db_session, cls)
    admin = _admin(db_session, str(cls.id))

    announcement = test_client.post(
        f"/api/v1/classes/{cls.id}/announcements",
        json={"title": "Lịch học", "content": "Học tại A101", "is_pinned": True},
        headers=_token(lecturer_user),
    )
    assert announcement.status_code == 200
    assert test_client.get(
        f"/api/v1/classes/{cls.id}/announcements", headers=_token(student_user)
    ).status_code == 200

    randomized = test_client.post(
        f"/api/v1/classes/{cls.id}/groups/randomize",
        json={"group_count": 2, "replace_existing": False},
        headers=_token(lecturer_user),
    )
    assert randomized.status_code == 200
    members = [member["student_id"] for group in randomized.json() for member in group["members"]]
    assert sorted(members) == sorted(set(members))
    assert second_student.id in members
    assert (
        test_client.post(
            f"/api/v1/classes/{cls.id}/groups/randomize",
            json={"members_per_group": 1, "replace_existing": False},
            headers=_token(lecturer_user),
        ).status_code
        == 409
    )

    system = test_client.post(
        "/api/v1/announcements",
        json={"title": "Bảo trì", "content": "Hệ thống bảo trì tối nay.", "is_pinned": False},
        headers=_token(admin),
    )
    assert system.status_code == 200
    assert (
        test_client.post(
            "/api/v1/announcements",
            json={"title": "Sai quyền", "content": "Không được phép."},
            headers=_token(lecturer_user),
        ).status_code
        == 403
    )
    first_notifications = test_client.get(
        "/api/v1/notifications", headers=_token(student_user)
    ).json()
    second_notifications = test_client.get(
        "/api/v1/notifications", headers=_token(second_user)
    ).json()
    assert first_notifications["unread_count"] >= 2
    assert second_notifications["unread_count"] >= 2
    target = first_notifications["items"][0]
    assert (
        test_client.post(
            f"/api/v1/notifications/{target['id']}/read", headers=_token(second_user)
        ).status_code
        == 404
    )
    assert db_session.query(Notification).filter(Notification.user_id == admin.id).count() == 0
