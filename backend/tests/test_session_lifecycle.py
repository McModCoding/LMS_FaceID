"""
test_session_lifecycle.py
Kiểm tra vòng đời buổi học: mở, đóng, mở lại, tự đóng, cửa sổ giờ.
Dùng clock giả (override_clock).
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, time, timedelta

import pytest
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
from app.services.session_lifecycle_service import (
    auto_close_overdue,
    close_session,
    lazy_auto_close,
    open_session,
    reopen_session,
)
from app.utils.clock import VN_TZ, override_clock

_UID = lambda: uuid.uuid4().hex[:8]  # noqa: E731


def _tok(user: User) -> str:
    return create_access_token(
        {"sub": str(user.id), "role": user.role.value, "token_version": user.token_version}
    )


def _make_user(db: Session, role: UserRole, uid: str) -> User:
    u = User(
        username=f"u_{role.value}_{uid}",
        email=f"u_{role.value}_{uid}@t.com",
        password_hash=get_password_hash("X"),
        role=role,
        is_active=True,
        must_change_password=False,
        is_deleted=False,
        token_version=1,
    )
    db.add(u)
    db.flush()
    return u


@pytest.fixture
def lifecycle_data(db_session: Session):
    uid = _UID()
    sem = Semester(name=f"HK_LC_{uid}", start_date=date(2026, 9, 1), end_date=date(2026, 12, 31))
    db_session.add(sem)
    sub = Subject(code=f"LC_{uid}", name="Môn LC", credits=3)
    db_session.add(sub)

    u_admin = _make_user(db_session, UserRole.admin, uid)
    u_lec = _make_user(db_session, UserRole.lecturer, uid)
    u_lec2 = _make_user(db_session, UserRole.lecturer, uid + "2")
    u_stu = _make_user(db_session, UserRole.student, uid)
    db_session.flush()

    lec = Lecturer(user_id=u_lec.id, code=f"LC_L_{uid}", full_name="GV", type=LecturerType.full_time, is_deleted=False)
    lec2 = Lecturer(user_id=u_lec2.id, code=f"LC_L2_{uid}", full_name="GV2", type=LecturerType.full_time, is_deleted=False)
    db_session.add_all([lec, lec2])
    db_session.flush()

    cls = Class(
        code=f"CLS_LC_{uid}",
        subject_id=sub.id,
        semester_id=sem.id,
        lecturer_id=lec.id,
        max_students=30,
        status=ClassStatus.active,
        late_after_min=10,
        absent_after_min=30,
        is_deleted=False,
    )
    db_session.add(cls)
    db_session.flush()

    stu = Student(user_id=u_stu.id, student_code=f"SV_LC_{uid}", full_name="SV Test", status=StudentStatus.studying, is_deleted=False)
    db_session.add(stu)
    db_session.flush()
    db_session.add(ClassStudent(class_id=cls.id, student_id=stu.id, status=ClassStudentStatus.enrolled))

    # Buổi học scheduled hôm nay 8:00-10:00
    today = date.today()
    sess_sched = SessionModel(
        class_id=cls.id, session_no=1, date=today,
        start_time=time(8, 0), end_time=time(10, 0), room="A101",
        status=SessionStatus.scheduled,
    )
    # Buổi học scheduled ngày mai
    sess_future = SessionModel(
        class_id=cls.id, session_no=2, date=today + timedelta(days=7),
        start_time=time(8, 0), end_time=time(10, 0), room="A101",
        status=SessionStatus.scheduled,
    )
    # Buổi draft (draft class)
    cls_draft = Class(
        code=f"CLS_DRAFT_{uid}", subject_id=sub.id, semester_id=sem.id,
        lecturer_id=lec.id, max_students=30, status=ClassStatus.draft, is_deleted=False,
    )
    db_session.add(cls_draft)
    db_session.flush()
    sess_draft_cls = SessionModel(
        class_id=cls_draft.id, session_no=1, date=today,
        start_time=time(8, 0), end_time=time(10, 0), room="A102",
        status=SessionStatus.scheduled,
    )
    db_session.add_all([sess_sched, sess_future, sess_draft_cls])
    db_session.commit()
    db_session.refresh(sess_sched)
    db_session.refresh(sess_future)
    db_session.refresh(sess_draft_cls)
    db_session.refresh(cls)
    db_session.refresh(cls_draft)

    return {
        "u_admin": u_admin, "u_lec": u_lec, "u_lec2": u_lec2, "u_stu": u_stu,
        "lec": lec, "lec2": lec2, "cls": cls, "cls_draft": cls_draft,
        "stu": stu, "sess_sched": sess_sched, "sess_future": sess_future,
        "sess_draft_cls": sess_draft_cls,
    }


# ── Mở buổi ──────────────────────────────────────────────────────────────────

def test_open_session_in_window(db_session: Session, lifecycle_data):
    """Mở buổi trong cửa sổ giờ — thành công."""
    d = lifecycle_data
    sess = d["sess_sched"]
    fixed = datetime.combine(sess.date, time(7, 45), tzinfo=VN_TZ)  # 15 phút trước giờ bắt đầu
    with override_clock(fixed):
        result = open_session(db_session, sess.id, d["u_lec"])
    assert result.status.value == "open"
    db_session.expire_all()
    assert db_session.get(SessionModel, sess.id).opened_by == d["u_lec"].id


def test_open_session_lecturer_of_class(db_session: Session, lifecycle_data):
    """Giảng viên lớp khác không mở được."""
    d = lifecycle_data
    sess = d["sess_sched"]
    fixed = datetime.combine(sess.date, time(7, 45), tzinfo=VN_TZ)
    with override_clock(fixed), pytest.raises(Exception) as exc_info:
        open_session(db_session, sess.id, d["u_lec2"])
    assert "FORBIDDEN" in str(exc_info.value.detail.get("code", ""))


def test_open_session_student_forbidden(db_session: Session, lifecycle_data):
    """Sinh viên không mở được buổi."""
    d = lifecycle_data
    sess = d["sess_sched"]
    fixed = datetime.combine(sess.date, time(7, 45), tzinfo=VN_TZ)
    with override_clock(fixed), pytest.raises(Exception) as exc_info:
        open_session(db_session, sess.id, d["u_stu"])
    assert "FORBIDDEN" in str(exc_info.value.detail.get("code", ""))


def test_open_session_draft_class_fails(db_session: Session, lifecycle_data):
    """Lớp draft không mở được buổi."""
    d = lifecycle_data
    sess = d["sess_draft_cls"]
    fixed = datetime.combine(sess.date, time(7, 45), tzinfo=VN_TZ)
    with override_clock(fixed), pytest.raises(Exception) as exc_info:
        open_session(db_session, sess.id, d["u_admin"])
    assert "CLASS_NOT_ACTIVE" in str(exc_info.value.detail.get("code", ""))


def test_open_session_outside_window_lecturer_fails(db_session: Session, lifecycle_data):
    """Giảng viên không mở được buổi ngoài cửa sổ giờ."""
    d = lifecycle_data
    sess = d["sess_sched"]
    # 2 tiếng sau giờ kết thúc = ngoài cửa sổ (SESSION_OPEN_AFTER_END_MIN=60 phút)
    fixed = datetime.combine(sess.date, time(12, 30), tzinfo=VN_TZ)
    with override_clock(fixed), pytest.raises(Exception) as exc_info:
        open_session(db_session, sess.id, d["u_lec"])
    assert "OUTSIDE_OPEN_WINDOW" in str(exc_info.value.detail.get("code", ""))


def test_open_session_outside_window_admin_no_reason_fails(db_session: Session, lifecycle_data):
    """Admin mở ngoài cửa sổ không có lý do → lỗi."""
    d = lifecycle_data
    sess = d["sess_sched"]
    fixed = datetime.combine(sess.date, time(12, 30), tzinfo=VN_TZ)
    with override_clock(fixed), pytest.raises(Exception) as exc_info:
        open_session(db_session, sess.id, d["u_admin"], reason=None)
    assert "REASON_REQUIRED" in str(exc_info.value.detail.get("code", ""))


def test_open_session_outside_window_admin_with_reason_ok(db_session: Session, lifecycle_data):
    """Admin mở ngoài cửa sổ có lý do → thành công."""
    d = lifecycle_data
    sess = d["sess_sched"]
    fixed = datetime.combine(sess.date, time(12, 30), tzinfo=VN_TZ)
    with override_clock(fixed):
        result = open_session(db_session, sess.id, d["u_admin"], reason="Demo buổi học bổ sung")
    assert result.status.value == "open"


def test_open_session_boundary_exact_window_start(db_session: Session, lifecycle_data):
    """Đúng biên cửa sổ mở (bắt đầu - 30 phút) → thành công."""
    d = lifecycle_data
    sess = d["sess_sched"]
    # Đúng 7:30 = 8:00 - 30 phút
    fixed = datetime.combine(sess.date, time(7, 30), tzinfo=VN_TZ)
    with override_clock(fixed):
        result = open_session(db_session, sess.id, d["u_lec"])
    assert result.status.value == "open"


def test_open_session_only_one_open_per_class(db_session: Session, lifecycle_data):
    """Chỉ một buổi open mỗi lớp."""
    d = lifecycle_data
    sess1 = d["sess_sched"]
    sess2 = d["sess_future"]

    # Mở buổi 1
    fixed = datetime.combine(sess1.date, time(7, 45), tzinfo=VN_TZ)
    with override_clock(fixed):
        open_session(db_session, sess1.id, d["u_admin"], reason="test")

    # Thử mở buổi 2 (future) → phải fail
    with override_clock(fixed), pytest.raises(Exception) as exc_info:
        open_session(db_session, sess2.id, d["u_admin"], reason="test")
    assert "SESSION_ALREADY_OPEN" in str(exc_info.value.detail.get("code", ""))


def test_open_already_open_session_fails(db_session: Session, lifecycle_data):
    """Mở buổi đã open → INVALID_STATE_TRANSITION."""
    d = lifecycle_data
    sess = d["sess_sched"]
    fixed = datetime.combine(sess.date, time(7, 45), tzinfo=VN_TZ)
    with override_clock(fixed):
        open_session(db_session, sess.id, d["u_lec"])
        db_session.expire_all()
        with pytest.raises(Exception) as exc_info:
            open_session(db_session, sess.id, d["u_lec"])
    assert "INVALID_STATE_TRANSITION" in str(exc_info.value.detail.get("code", ""))


# ── Đóng buổi ────────────────────────────────────────────────────────────────

def test_close_session_success(db_session: Session, lifecycle_data):
    """Đóng buổi open → closed."""
    d = lifecycle_data
    sess = d["sess_sched"]
    fixed = datetime.combine(sess.date, time(7, 45), tzinfo=VN_TZ)
    with override_clock(fixed):
        open_session(db_session, sess.id, d["u_lec"])
        db_session.expire_all()
        result = close_session(db_session, sess.id, d["u_lec"])
    assert result.status.value == "closed"
    assert result.closed_by == d["u_lec"].id


def test_close_scheduled_session_fails(db_session: Session, lifecycle_data):
    """Đóng buổi scheduled → INVALID_STATE_TRANSITION."""
    d = lifecycle_data
    sess = d["sess_sched"]
    with pytest.raises(Exception) as exc_info:
        close_session(db_session, sess.id, d["u_admin"])
    assert "INVALID_STATE_TRANSITION" in str(exc_info.value.detail.get("code", ""))


# ── Mở lại buổi ──────────────────────────────────────────────────────────────

def test_reopen_session_admin_only(db_session: Session, lifecycle_data):
    """Mở lại buổi: Admin OK, giảng viên → 403."""
    d = lifecycle_data
    sess = d["sess_sched"]
    fixed = datetime.combine(sess.date, time(7, 45), tzinfo=VN_TZ)
    with override_clock(fixed):
        open_session(db_session, sess.id, d["u_lec"])
        db_session.expire_all()
        close_session(db_session, sess.id, d["u_lec"])
        db_session.expire_all()

    # GV không được mở lại
    with pytest.raises(Exception) as exc_info:
        reopen_session(db_session, sess.id, d["u_lec"], reason="test")
    assert "FORBIDDEN" in str(exc_info.value.detail.get("code", ""))

    # Admin được mở lại
    result = reopen_session(db_session, sess.id, d["u_admin"], reason="Cần bổ sung điểm danh")
    assert result.status.value == "open"


def test_reopen_non_closed_fails(db_session: Session, lifecycle_data):
    """Mở lại buổi scheduled → INVALID_STATE_TRANSITION."""
    d = lifecycle_data
    sess = d["sess_sched"]
    with pytest.raises(Exception) as exc_info:
        reopen_session(db_session, sess.id, d["u_admin"], reason="test")
    assert "INVALID_STATE_TRANSITION" in str(exc_info.value.detail.get("code", ""))


def test_reopen_rejects_when_another_session_is_open(db_session: Session, lifecycle_data):
    """Mở lại không được tạo hai buổi open trong cùng lớp."""
    d = lifecycle_data
    original = d["sess_sched"]
    other = d["sess_future"]
    original.status = SessionStatus.closed
    original.closed_at = datetime.combine(original.date, time(10, 30), tzinfo=VN_TZ)
    other.status = SessionStatus.open
    other.opened_at = datetime.combine(other.date, time(8, 0), tzinfo=VN_TZ)
    db_session.commit()

    with pytest.raises(Exception) as exc_info:
        reopen_session(db_session, original.id, d["u_admin"], reason="Bổ sung dữ liệu")
    assert exc_info.value.detail["code"] == "SESSION_ALREADY_OPEN"


# ── Tự đóng ──────────────────────────────────────────────────────────────────

def test_auto_close_overdue(db_session: Session, lifecycle_data):
    """auto_close_overdue đóng buổi open quá SESSION_AUTO_CLOSE_AFTER_END_MIN."""
    d = lifecycle_data
    sess = d["sess_sched"]
    # Mở buổi trong cửa sổ
    open_time = datetime.combine(sess.date, time(7, 45), tzinfo=VN_TZ)
    with override_clock(open_time):
        open_session(db_session, sess.id, d["u_lec"])

    # Sau 2 tiếng 1 phút kể từ end_time (default 120 phút)
    # end_time = 10:00, auto_close = 12:01
    auto_close_time = datetime.combine(sess.date, time(12, 1), tzinfo=VN_TZ)
    with override_clock(auto_close_time):
        count = auto_close_overdue(db_session)

    assert count >= 1
    db_session.expire_all()
    updated = db_session.get(SessionModel, sess.id)
    assert updated.status == SessionStatus.closed
    assert updated.auto_closed is True
    assert updated.closed_by is None  # tự đóng không có người


def test_lazy_auto_close(db_session: Session, lifecycle_data):
    """lazy_auto_close tự đóng khi truy cập buổi quá hạn."""
    d = lifecycle_data
    sess = d["sess_future"]  # Buổi tương lai scheduled
    # Giả lập: mở buổi
    sess.status = SessionStatus.open
    sess.opened_at = datetime.combine(sess.date, time(8, 0), tzinfo=VN_TZ)
    db_session.flush()

    # Kiểm tra lazy tại 12:01 (quá 120 phút sau end_time 10:00)
    future_close_time = datetime.combine(sess.date, time(12, 1), tzinfo=VN_TZ)
    with override_clock(future_close_time):
        updated = lazy_auto_close(db_session, sess)

    assert updated.status == SessionStatus.closed
    assert updated.auto_closed is True


def test_dev_allow_open_anytime(db_session: Session, lifecycle_data, monkeypatch):
    """DEV_ALLOW_OPEN_ANYTIME bỏ qua kiểm tra cửa sổ giờ."""
    from app.core.config import settings
    monkeypatch.setattr(settings, "DEV_ALLOW_OPEN_ANYTIME", True)

    d = lifecycle_data
    sess = d["sess_sched"]
    # Giờ hoàn toàn ngoài cửa sổ
    far_future = datetime.combine(sess.date, time(23, 0), tzinfo=VN_TZ)
    with override_clock(far_future):
        result = open_session(db_session, sess.id, d["u_lec"])
    assert result.status.value == "open"
