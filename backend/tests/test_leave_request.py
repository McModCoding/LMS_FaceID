"""
test_leave_request.py
Kiểm tra đơn xin vắng: tạo, hủy, duyệt/từ chối.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, time, timedelta

import pytest

from app.core.security import get_password_hash
from app.models.attendance import (
    AttendanceRecord,
    AttendanceSource,
    AttendanceStatus,
    LeaveRequestStatus,
)
from app.models.audit import AuditLog
from app.models.class_ import Class, ClassStatus, ClassStudent, ClassStudentStatus
from app.models.lecturer import Lecturer, LecturerType
from app.models.semester import Semester
from app.models.session import Session as SessionModel
from app.models.session import SessionStatus
from app.models.student import Student, StudentStatus
from app.models.subject import Subject
from app.models.user import User, UserRole
from app.schemas.leave_request import LeaveRequestCreate, LeaveRequestReview
from app.services.leave_request_service import (
    cancel_leave_request,
    create_leave_request,
    review_leave_request,
)
from app.utils.clock import VN_TZ, override_clock

_UID = lambda: uuid.uuid4().hex[:8]  # noqa: E731


def _make_user(db, role, uid, sfx=""):
    u = User(username=f"lr_{role.value}_{uid}{sfx}", email=f"lr_{role.value}_{uid}{sfx}@t.com",
             password_hash=get_password_hash("X"), role=role, is_active=True,
             must_change_password=False, is_deleted=False, token_version=1)
    db.add(u)
    db.flush()
    return u


@pytest.fixture
def lr_data(db_session):
    uid = _UID()
    sem = Semester(name=f"HK_LR_{uid}", start_date=date(2026, 9, 1), end_date=date(2026, 12, 31))
    db_session.add(sem)
    sub = Subject(code=f"LR_{uid}", name="Môn LR", credits=3)
    db_session.add(sub)
    u_admin = _make_user(db_session, UserRole.admin, uid, "a")
    u_lec = _make_user(db_session, UserRole.lecturer, uid, "l")
    u_stu = _make_user(db_session, UserRole.student, uid, "s")
    u_stu2 = _make_user(db_session, UserRole.student, uid, "s2")  # SV không thuộc lớp
    db_session.flush()

    lec = Lecturer(user_id=u_lec.id, code=f"LR_L_{uid}", full_name="GV", type=LecturerType.full_time, is_deleted=False)
    db_session.add(lec)
    db_session.flush()

    cls = Class(code=f"CLS_LR_{uid}", subject_id=sub.id, semester_id=sem.id,
                lecturer_id=lec.id, max_students=30, status=ClassStatus.active,
                late_after_min=10, absent_after_min=30, is_deleted=False,
                attendance_warning_absences=3)
    db_session.add(cls)
    db_session.flush()

    stu = Student(user_id=u_stu.id, student_code=f"SV_LR_{uid}", full_name="SV", status=StudentStatus.studying, is_deleted=False)
    stu2 = Student(user_id=u_stu2.id, student_code=f"SV_LR_{uid}2", full_name="SV2", status=StudentStatus.studying, is_deleted=False)
    db_session.add_all([stu, stu2])
    db_session.flush()
    db_session.add(ClassStudent(class_id=cls.id, student_id=stu.id, status=ClassStudentStatus.enrolled))
    db_session.flush()

    today = date.today()
    # Buổi tương lai (scheduled)
    sess_future = SessionModel(class_id=cls.id, session_no=1,
                               date=today + timedelta(days=3),
                               start_time=time(8, 0), end_time=time(10, 0),
                               room="A1", status=SessionStatus.scheduled)
    # Buổi hôm qua (closed, trong 7 ngày)
    sess_yesterday = SessionModel(class_id=cls.id, session_no=2,
                                  date=today - timedelta(days=1),
                                  start_time=time(8, 0), end_time=time(10, 0),
                                  room="A1", status=SessionStatus.closed,
                                  opened_at=datetime.combine(today - timedelta(days=1), time(7, 50), tzinfo=VN_TZ),
                                  closed_at=datetime.combine(today - timedelta(days=1), time(10, 5), tzinfo=VN_TZ))
    # Buổi 8 ngày trước (quá 7 ngày)
    sess_old = SessionModel(class_id=cls.id, session_no=3,
                            date=today - timedelta(days=8),
                            start_time=time(8, 0), end_time=time(10, 0),
                            room="A1", status=SessionStatus.closed,
                            opened_at=datetime.combine(today - timedelta(days=8), time(7, 50), tzinfo=VN_TZ),
                            closed_at=datetime.combine(today - timedelta(days=8), time(10, 5), tzinfo=VN_TZ))
    # Buổi open hôm nay
    sess_open = SessionModel(class_id=cls.id, session_no=4,
                             date=today, start_time=time(8, 0), end_time=time(10, 0),
                             room="A1", status=SessionStatus.open,
                             opened_at=datetime.combine(today, time(7, 50), tzinfo=VN_TZ))
    db_session.add_all([sess_future, sess_yesterday, sess_old, sess_open])
    db_session.commit()
    for x in [sess_future, sess_yesterday, sess_old, sess_open, cls, stu, stu2]:
        db_session.refresh(x)

    return {
        "u_admin": u_admin, "u_lec": u_lec, "u_stu": u_stu, "u_stu2": u_stu2,
        "lec": lec, "cls": cls, "stu": stu, "stu2": stu2,
        "sess_future": sess_future, "sess_yesterday": sess_yesterday,
        "sess_old": sess_old, "sess_open": sess_open,
    }


# ── Tạo đơn ──────────────────────────────────────────────────────────────────

def test_create_leave_request_future_session(db_session, lr_data):
    """Gửi đơn cho buổi tương lai → OK."""
    d = lr_data
    data = LeaveRequestCreate(session_id=d["sess_future"].id, reason="Đi khám bệnh.")
    result = create_leave_request(db_session, d["stu"].id, data)
    assert result.status == LeaveRequestStatus.pending
    audit = db_session.query(AuditLog).filter(
        AuditLog.action == "CREATE_LEAVE_REQUEST",
        AuditLog.entity_id == str(result.id),
    ).one()
    assert audit.user_id == d["u_stu"].id


def test_create_leave_request_past_7_days(db_session, lr_data):
    """Gửi đơn cho buổi trong 7 ngày qua → OK."""
    d = lr_data
    data = LeaveRequestCreate(session_id=d["sess_yesterday"].id, reason="Gia đình có việc.")
    result = create_leave_request(db_session, d["stu"].id, data)
    assert result.status == LeaveRequestStatus.pending


def test_create_leave_request_too_old_fails(db_session, lr_data):
    """Gửi đơn cho buổi quá 7 ngày → 400 SESSION_TOO_OLD."""
    d = lr_data
    data = LeaveRequestCreate(session_id=d["sess_old"].id, reason="Lý do muộn.")
    with pytest.raises(Exception) as exc_info:
        create_leave_request(db_session, d["stu"].id, data)
    assert "SESSION_TOO_OLD" in str(exc_info.value.detail.get("code", ""))


def test_create_leave_request_not_enrolled_fails(db_session, lr_data):
    """Sinh viên không thuộc lớp → 403 NOT_ENROLLED."""
    d = lr_data
    data = LeaveRequestCreate(session_id=d["sess_future"].id, reason="Tôi không học lớp này.")
    with pytest.raises(Exception) as exc_info:
        create_leave_request(db_session, d["stu2"].id, data)
    assert "NOT_ENROLLED" in str(exc_info.value.detail.get("code", ""))


def test_create_leave_request_duplicate_pending_fails(db_session, lr_data):
    """Mỗi (sinh viên, buổi) chỉ một đơn pending."""
    d = lr_data
    data = LeaveRequestCreate(session_id=d["sess_future"].id, reason="Lý do 1.")
    create_leave_request(db_session, d["stu"].id, data)
    with pytest.raises(Exception) as exc_info:
        create_leave_request(db_session, d["stu"].id, data)
    assert "DUPLICATE_PENDING_REQUEST" in str(exc_info.value.detail.get("code", ""))


# ── Hủy đơn ──────────────────────────────────────────────────────────────────

def test_cancel_pending_request(db_session, lr_data):
    """Sinh viên hủy đơn pending của mình → OK."""
    d = lr_data
    data = LeaveRequestCreate(session_id=d["sess_future"].id, reason="Có việc.")
    created = create_leave_request(db_session, d["stu"].id, data)
    result = cancel_leave_request(db_session, created.id, d["stu"].id, d["u_stu"].id)
    assert result.status == LeaveRequestStatus.rejected  # cancelled = rejected


def test_cancel_other_student_request_forbidden(db_session, lr_data):
    """Sinh viên khác hủy đơn → 403."""
    d = lr_data
    data = LeaveRequestCreate(session_id=d["sess_future"].id, reason="Có việc.")
    created = create_leave_request(db_session, d["stu"].id, data)
    with pytest.raises(Exception) as exc_info:
        cancel_leave_request(db_session, created.id, d["stu2"].id, d["u_stu2"].id)
    assert "FORBIDDEN" in str(exc_info.value.detail.get("code", ""))


# ── Duyệt / từ chối ──────────────────────────────────────────────────────────

def test_approve_before_session_opens(db_session, lr_data):
    """Duyệt trước khi buổi mở → status approved, chưa có attendance record (sẽ áp khi mở)."""
    d = lr_data
    data = LeaveRequestCreate(session_id=d["sess_future"].id, reason="Ốm nặng.")
    created = create_leave_request(db_session, d["stu"].id, data)
    review = LeaveRequestReview(decision="approve", review_note="Chấp nhận.")
    result = review_leave_request(db_session, created.id, d["u_admin"], review)
    assert result.status == LeaveRequestStatus.approved
    # Chưa có attendance record cho buổi future
    rec = db_session.query(AttendanceRecord).filter(
        AttendanceRecord.session_id == d["sess_future"].id,
        AttendanceRecord.student_id == d["stu"].id,
    ).first()
    assert rec is None


def test_approve_absent_system_becomes_excused(db_session, lr_data):
    """Duyệt khi bản ghi absent/system → excused/leave."""
    d = lr_data
    # Tạo bản ghi absent/system cho sess_open
    rec = AttendanceRecord(
        session_id=d["sess_open"].id, student_id=d["stu"].id,
        status=AttendanceStatus.absent, source=AttendanceSource.system,
    )
    db_session.add(rec)
    db_session.flush()

    data = LeaveRequestCreate(session_id=d["sess_open"].id, reason="Lý do.")
    created = create_leave_request(db_session, d["stu"].id, data)
    review = LeaveRequestReview(decision="approve")
    review_leave_request(db_session, created.id, d["u_admin"], review)

    db_session.expire_all()
    updated_rec = db_session.query(AttendanceRecord).filter(
        AttendanceRecord.session_id == d["sess_open"].id,
        AttendanceRecord.student_id == d["stu"].id,
    ).first()
    assert updated_rec.status == AttendanceStatus.excused
    assert updated_rec.source == AttendanceSource.leave


def test_approve_present_not_changed(db_session, lr_data):
    """Duyệt khi bản ghi đang present → giữ nguyên."""
    d = lr_data
    rec = AttendanceRecord(
        session_id=d["sess_open"].id, student_id=d["stu"].id,
        status=AttendanceStatus.present, source=AttendanceSource.manual,
    )
    db_session.add(rec)
    db_session.flush()

    data = LeaveRequestCreate(session_id=d["sess_open"].id, reason="Lý do.")
    created = create_leave_request(db_session, d["stu"].id, data)
    review = LeaveRequestReview(decision="approve")
    review_leave_request(db_session, created.id, d["u_admin"], review)

    db_session.expire_all()
    unchanged = db_session.query(AttendanceRecord).filter(
        AttendanceRecord.session_id == d["sess_open"].id,
        AttendanceRecord.student_id == d["stu"].id,
    ).first()
    assert unchanged.status == AttendanceStatus.present


def test_reject_not_change_attendance(db_session, lr_data):
    """Từ chối không đổi điểm danh."""
    d = lr_data
    rec = AttendanceRecord(
        session_id=d["sess_open"].id, student_id=d["stu"].id,
        status=AttendanceStatus.absent, source=AttendanceSource.system,
    )
    db_session.add(rec)
    db_session.flush()

    data = LeaveRequestCreate(session_id=d["sess_open"].id, reason="Lý do.")
    created = create_leave_request(db_session, d["stu"].id, data)
    review = LeaveRequestReview(decision="reject", review_note="Không đủ lý do.")
    review_leave_request(db_session, created.id, d["u_admin"], review)

    db_session.expire_all()
    unchanged = db_session.query(AttendanceRecord).filter(
        AttendanceRecord.session_id == d["sess_open"].id,
        AttendanceRecord.student_id == d["stu"].id,
    ).first()
    assert unchanged.status == AttendanceStatus.absent  # không đổi


def test_approve_after_close_window_expired_lecturer_fails(db_session, lr_data, monkeypatch):
    """Duyệt buổi closed hết cửa sổ → GV bị 403, Admin OK."""
    from app.core.config import settings
    monkeypatch.setattr(settings, "EDIT_AFTER_CLOSE_HOURS", 0)

    d = lr_data
    rec = AttendanceRecord(
        session_id=d["sess_yesterday"].id, student_id=d["stu"].id,
        status=AttendanceStatus.absent, source=AttendanceSource.system,
    )
    db_session.add(rec)
    db_session.flush()

    data = LeaveRequestCreate(session_id=d["sess_yesterday"].id, reason="Ốm.")
    created = create_leave_request(db_session, d["stu"].id, data)
    review = LeaveRequestReview(decision="approve")

    closed_at = d["sess_yesterday"].closed_at or datetime.now(VN_TZ)
    if closed_at.tzinfo is None:
        closed_at = closed_at.replace(tzinfo=VN_TZ)
    future = closed_at + timedelta(hours=1)
    with override_clock(future), pytest.raises(Exception) as exc_info:
        review_leave_request(db_session, created.id, d["u_lec"], review)
    assert "EDIT_WINDOW_EXPIRED" in str(exc_info.value.detail.get("code", ""))

    # Admin OK dù quá cửa sổ
    with override_clock(future):
        result = review_leave_request(db_session, created.id, d["u_admin"], review)
    assert result.status == LeaveRequestStatus.approved
