"""
test_attendance.py
Kiểm tra ensure_records, apply_presence (mốc giờ), patch, bulk, mark_remaining, history.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, time, timedelta

import pytest
from sqlalchemy.orm import Session

from app.core.security import get_password_hash
from app.models.attendance import (
    AttendanceRecord,
    AttendanceSource,
    AttendanceStatus,
    LeaveRequest,
    LeaveRequestStatus,
)
from app.models.class_ import Class, ClassStatus, ClassStudent, ClassStudentStatus
from app.models.lecturer import Lecturer, LecturerType
from app.models.semester import Semester
from app.models.session import Session as SessionModel
from app.models.session import SessionStatus
from app.models.student import Student, StudentStatus
from app.models.subject import Subject
from app.models.user import User, UserRole
from app.schemas.attendance import AttendancePatch, BulkAttendancePatch, MarkRemainingPatch
from app.services.attendance_service import (
    apply_presence,
    bulk_patch_attendance,
    check_in_student,
    ensure_records,
    get_attendance_history,
    mark_remaining_attendance,
    patch_attendance,
)
from app.utils.clock import VN_TZ, now_local, override_clock

_UID = lambda: uuid.uuid4().hex[:8]  # noqa: E731


def _make_user(db: Session, role: UserRole, uid: str, suffix: str = "") -> User:
    u = User(
        username=f"u_{role.value}_{uid}{suffix}",
        email=f"u_{role.value}_{uid}{suffix}@t.com",
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
def att_data(db_session: Session):
    uid = _UID()
    sem = Semester(name=f"HK_ATT_{uid}", start_date=date(2026, 9, 1), end_date=date(2026, 12, 31))
    db_session.add(sem)
    sub = Subject(code=f"ATT_{uid}", name="Môn ATT", credits=3)
    db_session.add(sub)
    u_admin = _make_user(db_session, UserRole.admin, uid)
    u_lec = _make_user(db_session, UserRole.lecturer, uid)
    db_session.flush()

    lec = Lecturer(user_id=u_lec.id, code=f"ATT_L_{uid}", full_name="GV", type=LecturerType.full_time, is_deleted=False)
    db_session.add(lec)
    db_session.flush()

    cls = Class(
        code=f"CLS_ATT_{uid}", subject_id=sub.id, semester_id=sem.id, lecturer_id=lec.id,
        max_students=30, status=ClassStatus.active,
        late_after_min=10, absent_after_min=30,
        weight_present=1.0, weight_late=0.5, weight_excused=1.0,
        attendance_warning_absences=3,
        is_deleted=False,
    )
    db_session.add(cls)
    db_session.flush()

    # 3 sinh viên
    students = []
    for i in range(3):
        u = _make_user(db_session, UserRole.student, uid, str(i))
        stu = Student(user_id=u.id, student_code=f"SV_ATT_{uid}_{i}", full_name=f"SV {i}", status=StudentStatus.studying, is_deleted=False)
        db_session.add(stu)
        db_session.flush()
        db_session.add(ClassStudent(class_id=cls.id, student_id=stu.id, status=ClassStudentStatus.enrolled))
        students.append((u, stu))
    db_session.flush()

    today = date.today()
    now = now_local()
    # Buổi hôm nay (để test mốc giờ)
    sess_open = SessionModel(
        class_id=cls.id, session_no=1, date=today,
        start_time=time(8, 0), end_time=time(10, 0), room="A1",
        status=SessionStatus.open,
        opened_at=now - timedelta(minutes=10),
    )
    # Buổi đã closed (hôm nay, 2 tiếng trước)
    sess_closed = SessionModel(
        class_id=cls.id, session_no=2, date=today,
        start_time=time(8, 0), end_time=time(10, 0), room="A1",
        status=SessionStatus.closed,
        opened_at=now - timedelta(hours=4),
        closed_at=now - timedelta(hours=2),
    )
    db_session.add_all([sess_open, sess_closed])
    db_session.commit()
    for x in [sess_open, sess_closed, cls]:
        db_session.refresh(x)

    return {
        "u_admin": u_admin, "u_lec": u_lec, "lec": lec, "cls": cls,
        "students": students,  # list of (user, student)
        "sess_open": sess_open, "sess_closed": sess_closed,
    }


# ── ensure_records ────────────────────────────────────────────────────────────

def test_ensure_records_creates_for_enrolled(db_session: Session, att_data):
    """ensure_records tạo bản ghi absent/system cho mọi sinh viên enrolled."""
    d = att_data
    count = ensure_records(db_session, d["sess_open"])
    assert count == 3
    recs = db_session.query(AttendanceRecord).filter(
        AttendanceRecord.session_id == d["sess_open"].id
    ).all()
    assert len(recs) == 3
    for r in recs:
        assert r.status == AttendanceStatus.absent
        assert r.source == AttendanceSource.system


def test_ensure_records_idempotent(db_session: Session, att_data):
    """Gọi ensure_records hai lần không tạo trùng."""
    d = att_data
    c1 = ensure_records(db_session, d["sess_open"])
    assert c1 == 3
    c2 = ensure_records(db_session, d["sess_open"])
    assert c2 == 0  # lần 2 không tạo mới
    total = db_session.query(AttendanceRecord).filter(
        AttendanceRecord.session_id == d["sess_open"].id
    ).count()
    assert total == 3


def test_ensure_records_approved_leave_becomes_excused(db_session: Session, att_data):
    """Đơn approved trước khi mở → excused/leave khi ensure_records."""
    d = att_data
    _, stu = d["students"][0]
    # Tạo đơn approved cho sess_open
    lr = LeaveRequest(
        student_id=stu.id,
        session_id=d["sess_open"].id,
        reason="Ốm",
        status=LeaveRequestStatus.approved,
        reviewed_by=d["u_admin"].id,
        reviewed_at=datetime.now(VN_TZ),
    )
    db_session.add(lr)
    db_session.flush()

    ensure_records(db_session, d["sess_open"])
    rec = db_session.query(AttendanceRecord).filter(
        AttendanceRecord.session_id == d["sess_open"].id,
        AttendanceRecord.student_id == stu.id,
    ).first()
    assert rec.status == AttendanceStatus.excused
    assert rec.source == AttendanceSource.leave


def test_ensure_records_dropped_student_kept(db_session: Session, att_data):
    """Sinh viên rút (dropped) vẫn giữ bản ghi lịch sử."""
    d = att_data
    _, stu = d["students"][2]
    # Tạo bản ghi trước
    ensure_records(db_session, d["sess_open"])
    # Rút sinh viên
    cs = db_session.query(ClassStudent).filter(
        ClassStudent.class_id == d["cls"].id,
        ClassStudent.student_id == stu.id,
    ).first()
    cs.status = ClassStudentStatus.dropped
    db_session.flush()

    # Gọi ensure lại — bản ghi cũ phải còn
    ensure_records(db_session, d["sess_open"])
    recs = db_session.query(AttendanceRecord).filter(
        AttendanceRecord.session_id == d["sess_open"].id,
        AttendanceRecord.student_id == stu.id,
    ).all()
    assert len(recs) == 1  # vẫn giữ bản ghi gốc


# ── apply_presence (mốc giờ) ─────────────────────────────────────────────────

def test_apply_presence_on_time_present(db_session: Session, att_data):
    """Đến trước late_after_min (10 phút) → present."""
    d = att_data
    ensure_records(db_session, d["sess_open"])
    _, stu = d["students"][0]
    # 8:05 — trước late_after_min 8:10
    fixed = datetime.combine(d["sess_open"].date, time(8, 5), tzinfo=VN_TZ)
    with override_clock(fixed):
        rec, code = apply_presence(db_session, d["sess_open"], stu.id, AttendanceSource.manual)
    assert code == "present"
    assert rec.status == AttendanceStatus.present


def test_apply_presence_at_late_boundary_present(db_session: Session, att_data):
    """Đúng late_after_min (8:10) → present (<=, không phải <)."""
    d = att_data
    ensure_records(db_session, d["sess_open"])
    _, stu = d["students"][0]
    fixed = datetime.combine(d["sess_open"].date, time(8, 10), tzinfo=VN_TZ)
    with override_clock(fixed):
        rec, code = apply_presence(db_session, d["sess_open"], stu.id, AttendanceSource.manual)
    assert code == "present"
    assert rec.status == AttendanceStatus.present


def test_apply_presence_over_late_boundary_late(db_session: Session, att_data):
    """Sau late_after_min 1 phút (8:11) → late."""
    d = att_data
    ensure_records(db_session, d["sess_open"])
    _, stu = d["students"][0]
    fixed = datetime.combine(d["sess_open"].date, time(8, 11), tzinfo=VN_TZ)
    with override_clock(fixed):
        rec, code = apply_presence(db_session, d["sess_open"], stu.id, AttendanceSource.manual)
    assert code == "late"
    assert rec.status == AttendanceStatus.late


def test_apply_presence_at_absent_boundary_late(db_session: Session, att_data):
    """Đúng absent_after_min (8:30) → late."""
    d = att_data
    ensure_records(db_session, d["sess_open"])
    _, stu = d["students"][0]
    fixed = datetime.combine(d["sess_open"].date, time(8, 30), tzinfo=VN_TZ)
    with override_clock(fixed):
        rec, code = apply_presence(db_session, d["sess_open"], stu.id, AttendanceSource.manual)
    assert code == "late"


def test_apply_presence_outside_window(db_session: Session, att_data):
    """Sau absent_after_min → OUTSIDE_WINDOW, không đổi trạng thái."""
    d = att_data
    ensure_records(db_session, d["sess_open"])
    _, stu = d["students"][0]
    fixed = datetime.combine(d["sess_open"].date, time(8, 31), tzinfo=VN_TZ)
    with override_clock(fixed):
        rec, code = apply_presence(db_session, d["sess_open"], stu.id, AttendanceSource.manual)
    assert code == "OUTSIDE_WINDOW"
    assert rec.status == AttendanceStatus.absent  # không đổi


def test_apply_presence_no_downgrade(db_session: Session, att_data):
    """Không hạ cấp present/late."""
    d = att_data
    ensure_records(db_session, d["sess_open"])
    _, stu = d["students"][0]

    # Đặt present
    fixed = datetime.combine(d["sess_open"].date, time(8, 5), tzinfo=VN_TZ)
    with override_clock(fixed):
        rec, _ = apply_presence(db_session, d["sess_open"], stu.id, AttendanceSource.manual)
    assert rec.status == AttendanceStatus.present

    # Cố gọi lại (sẽ trả no_downgrade, không đổi)
    with override_clock(fixed):
        rec2, code = apply_presence(db_session, d["sess_open"], stu.id, AttendanceSource.manual)
    assert code == "no_downgrade"
    assert rec2.status == AttendanceStatus.present
    assert rec2.hit_count == 2  # hit_count tăng


def test_apply_presence_excused_kept(db_session: Session, att_data):
    """excused không bị đổi bởi apply_presence."""
    d = att_data
    ensure_records(db_session, d["sess_open"])
    _, stu = d["students"][0]
    # Set excused trực tiếp
    rec = db_session.query(AttendanceRecord).filter(
        AttendanceRecord.session_id == d["sess_open"].id,
        AttendanceRecord.student_id == stu.id,
    ).first()
    rec.status = AttendanceStatus.excused
    rec.source = AttendanceSource.leave
    db_session.flush()

    fixed = datetime.combine(d["sess_open"].date, time(8, 5), tzinfo=VN_TZ)
    with override_clock(fixed):
        rec2, code = apply_presence(db_session, d["sess_open"], stu.id, AttendanceSource.manual)
    assert code == "already_excused"
    assert rec2.status == AttendanceStatus.excused


# ── patch_attendance ──────────────────────────────────────────────────────────

def test_patch_attendance_system_to_status_no_note_required(db_session: Session, att_data):
    """Chuyển từ mặc định system trong buổi open → không cần note."""
    d = att_data
    ensure_records(db_session, d["sess_open"])
    _, stu = d["students"][0]
    data = AttendancePatch(status=AttendanceStatus.present, note=None)
    rec = patch_attendance(db_session, d["sess_open"].id, stu.id, data, d["u_lec"])
    assert rec.status == AttendanceStatus.present
    assert rec.source == AttendanceSource.manual


def test_patch_attendance_manual_to_status_note_required(db_session: Session, att_data):
    """Sửa bản ghi đã do người đặt → phải có note."""
    d = att_data
    ensure_records(db_session, d["sess_open"])
    _, stu = d["students"][0]
    # Đặt bản ghi manual trước
    data1 = AttendancePatch(status=AttendanceStatus.present, note=None)
    patch_attendance(db_session, d["sess_open"].id, stu.id, data1, d["u_lec"])

    # Sửa lại không có note → lỗi
    data2 = AttendancePatch(status=AttendanceStatus.late, note=None)
    with pytest.raises(Exception) as exc_info:
        patch_attendance(db_session, d["sess_open"].id, stu.id, data2, d["u_lec"])
    assert "NOTE_REQUIRED" in str(exc_info.value.detail.get("code", ""))


def test_patch_attendance_closed_session_note_required(db_session: Session, att_data):
    """Sửa buổi đã closed → phải có note."""
    d = att_data
    ensure_records(db_session, d["sess_closed"])
    _, stu = d["students"][0]
    data = AttendancePatch(status=AttendanceStatus.present, note=None)
    with pytest.raises(Exception) as exc_info:
        patch_attendance(db_session, d["sess_closed"].id, stu.id, data, d["u_lec"])
    assert "NOTE_REQUIRED" in str(exc_info.value.detail.get("code", ""))


def test_patch_attendance_expected_status_stale(db_session: Session, att_data):
    """expected_status lệch → 409 STALE_STATE."""
    d = att_data
    ensure_records(db_session, d["sess_open"])
    _, stu = d["students"][0]
    # Thực tế là absent, expected_status=present → stale
    data = AttendancePatch(
        status=AttendanceStatus.late,
        note=None,
        expected_status=AttendanceStatus.present,
    )
    with pytest.raises(Exception) as exc_info:
        patch_attendance(db_session, d["sess_open"].id, stu.id, data, d["u_lec"])
    assert "STALE_STATE" in str(exc_info.value.detail.get("code", ""))


def test_patch_attendance_closed_within_24h_lecturer_ok(db_session: Session, att_data):
    """GV sửa buổi closed trong 24h → OK (với note)."""
    d = att_data
    ensure_records(db_session, d["sess_closed"])
    _, stu = d["students"][0]
    data = AttendancePatch(status=AttendanceStatus.present, note="Nhầm lúc điểm danh")
    rec = patch_attendance(db_session, d["sess_closed"].id, stu.id, data, d["u_lec"])
    assert rec.status == AttendanceStatus.present


def test_patch_attendance_closed_expired_lecturer_403(db_session: Session, att_data, monkeypatch):
    """GV sửa buổi closed sau 24h → 403 EDIT_WINDOW_EXPIRED."""
    from app.core.config import settings
    monkeypatch.setattr(settings, "EDIT_AFTER_CLOSE_HOURS", 0)  # cửa sổ 0h = đã hết ngay

    d = att_data
    ensure_records(db_session, d["sess_closed"])
    _, stu = d["students"][0]
    data = AttendancePatch(status=AttendanceStatus.present, note="Sửa muộn")

    # Giả lập giờ sau closed_at
    closed_at = d["sess_closed"].closed_at or datetime.now(VN_TZ)
    if closed_at.tzinfo is None:
        closed_at = closed_at.replace(tzinfo=VN_TZ)
    future = closed_at + timedelta(hours=1)
    with override_clock(future), pytest.raises(Exception) as exc_info:
        patch_attendance(db_session, d["sess_closed"].id, stu.id, data, d["u_lec"])
    assert "EDIT_WINDOW_EXPIRED" in str(exc_info.value.detail.get("code", ""))


def test_patch_attendance_closed_admin_always_ok(db_session: Session, att_data, monkeypatch):
    """Admin sửa buổi closed mọi lúc → OK."""
    from app.core.config import settings
    monkeypatch.setattr(settings, "EDIT_AFTER_CLOSE_HOURS", 0)

    d = att_data
    ensure_records(db_session, d["sess_closed"])
    _, stu = d["students"][0]
    data = AttendancePatch(status=AttendanceStatus.present, note="Admin sửa")

    closed_at = d["sess_closed"].closed_at or datetime.now(VN_TZ)
    if closed_at.tzinfo is None:
        closed_at = closed_at.replace(tzinfo=VN_TZ)
    future = closed_at + timedelta(hours=1)
    with override_clock(future):
        rec = patch_attendance(db_session, d["sess_closed"].id, stu.id, data, d["u_admin"])
    assert rec.status == AttendanceStatus.present


def test_patch_attendance_history_recorded(db_session: Session, att_data):
    """Mỗi lần patch tạo một dòng history."""
    d = att_data
    ensure_records(db_session, d["sess_open"])
    _, stu = d["students"][0]
    data = AttendancePatch(status=AttendanceStatus.present, note=None)
    rec = patch_attendance(db_session, d["sess_open"].id, stu.id, data, d["u_lec"])
    assert rec.status == AttendanceStatus.present
    history = get_attendance_history(db_session, d["sess_open"].id, stu.id)
    assert len(history) == 1
    assert history[0].new_status == AttendanceStatus.present
    assert history[0].old_status == AttendanceStatus.absent


# ── bulk & mark_remaining ─────────────────────────────────────────────────────

def test_bulk_patch_attendance(db_session: Session, att_data):
    """Bulk patch nhiều sinh viên."""
    d = att_data
    ensure_records(db_session, d["sess_open"])
    student_ids = [stu.id for _, stu in d["students"]]
    data = BulkAttendancePatch(student_ids=student_ids, status=AttendanceStatus.present, note=None)
    result = bulk_patch_attendance(db_session, d["sess_open"].id, data, d["u_lec"])
    assert result.updated == 3


def test_mark_remaining(db_session: Session, att_data):
    """mark_remaining áp absent cho các bản ghi pending."""
    d = att_data
    ensure_records(db_session, d["sess_open"])
    # Đặt 1 sinh viên present trước
    _, stu0 = d["students"][0]
    p_data = AttendancePatch(status=AttendanceStatus.present, note=None)
    patch_attendance(db_session, d["sess_open"].id, stu0.id, p_data, d["u_lec"])

    # mark_remaining với absent
    mr_data = MarkRemainingPatch(status=AttendanceStatus.absent, note="Điểm danh hết buổi")
    result = mark_remaining_attendance(db_session, d["sess_open"].id, mr_data, d["u_lec"])
    # Chỉ 2 bản ghi còn pending (stu1, stu2) → updated=2
    assert result.updated == 2


def test_bulk_and_mark_remaining_closed_session_require_note(db_session: Session, att_data):
    """Không được sửa hàng loạt buổi đã đóng mà thiếu lý do."""
    d = att_data
    ensure_records(db_session, d["sess_closed"])
    student_ids = [student.id for _, student in d["students"]]

    with pytest.raises(Exception) as bulk_error:
        bulk_patch_attendance(
            db_session,
            d["sess_closed"].id,
            BulkAttendancePatch(student_ids=student_ids, status=AttendanceStatus.present),
            d["u_lec"],
        )
    assert bulk_error.value.detail["code"] == "NOTE_REQUIRED"

    with pytest.raises(Exception) as mark_error:
        mark_remaining_attendance(
            db_session,
            d["sess_closed"].id,
            MarkRemainingPatch(status=AttendanceStatus.absent),
            d["u_lec"],
        )
    assert mark_error.value.detail["code"] == "NOTE_REQUIRED"


def test_check_in_commits_hit_count_when_status_is_already_set(db_session: Session, att_data):
    """Check-in lặp vẫn phải lưu hit_count, dù không đổi trạng thái."""
    d = att_data
    ensure_records(db_session, d["sess_open"])
    _, student = d["students"][0]
    record = db_session.query(AttendanceRecord).filter(
        AttendanceRecord.session_id == d["sess_open"].id,
        AttendanceRecord.student_id == student.id,
    ).first()
    record.status = AttendanceStatus.present
    record.source = AttendanceSource.manual
    record.hit_count = 1
    db_session.commit()

    fixed = datetime.combine(d["sess_open"].date, time(8, 5), tzinfo=VN_TZ)
    with override_clock(fixed):
        result = check_in_student(db_session, d["sess_open"].id, student.id, d["u_lec"])
    assert result.result_code == "no_downgrade"
    db_session.expire_all()
    persisted = db_session.query(AttendanceRecord).filter(
        AttendanceRecord.session_id == d["sess_open"].id,
        AttendanceRecord.student_id == student.id,
    ).first()
    assert persisted.hit_count == 2
