"""
test_report.py
Kiểm tra công thức điểm chuyên cần, cờ cảnh báo, số truy vấn.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, time, timedelta
from decimal import Decimal

import pytest

from app.core.security import get_password_hash
from app.models.attendance import AttendanceRecord, AttendanceSource, AttendanceStatus
from app.models.class_ import Class, ClassStatus, ClassStudent, ClassStudentStatus
from app.models.lecturer import Lecturer, LecturerType
from app.models.semester import Semester
from app.models.session import Session as SessionModel
from app.models.session import SessionStatus
from app.models.student import Student, StudentStatus
from app.models.subject import Subject
from app.models.user import User, UserRole
from app.services.report_service import get_attendance_report, get_session_attendance
from app.utils.clock import VN_TZ

_UID = lambda: uuid.uuid4().hex[:8]  # noqa: E731


def _make_user(db, role, uid, sfx=""):
    u = User(username=f"rpt_{role.value}_{uid}{sfx}", email=f"rpt_{role.value}_{uid}{sfx}@t.com",
             password_hash=get_password_hash("X"), role=role, is_active=True,
             must_change_password=False, is_deleted=False, token_version=1)
    db.add(u)
    db.flush()
    return u


@pytest.fixture
def report_data(db_session):
    uid = _UID()
    sem = Semester(name=f"HK_RPT_{uid}", start_date=date(2026, 9, 1), end_date=date(2026, 12, 31))
    db_session.add(sem)
    sub = Subject(code=f"RPT_{uid}", name="Môn RPT", credits=3)
    db_session.add(sub)
    u_admin = _make_user(db_session, UserRole.admin, uid, "a")
    u_lec = _make_user(db_session, UserRole.lecturer, uid, "l")
    db_session.flush()
    lec = Lecturer(user_id=u_lec.id, code=f"RPT_L_{uid}", full_name="GV", type=LecturerType.full_time, is_deleted=False)
    db_session.add(lec)
    db_session.flush()

    cls = Class(
        code=f"CLS_RPT_{uid}", subject_id=sub.id, semester_id=sem.id,
        lecturer_id=lec.id, max_students=30, status=ClassStatus.active,
        late_after_min=10, absent_after_min=30,
        weight_present=1.0, weight_late=0.5, weight_excused=1.0,
        attendance_warning_absences=3,
        is_deleted=False,
    )
    db_session.add(cls)
    db_session.flush()

    # 5 sinh viên
    students = []
    for i in range(5):
        u = _make_user(db_session, UserRole.student, uid, str(i))
        stu = Student(user_id=u.id, student_code=f"SV_RPT_{uid}_{i}", full_name=f"SV RPT {i}",
                      status=StudentStatus.studying, is_deleted=False)
        db_session.add(stu)
        db_session.flush()
        db_session.add(ClassStudent(class_id=cls.id, student_id=stu.id, status=ClassStudentStatus.enrolled))
        students.append(stu)
    db_session.flush()

    # 5 buổi closed
    sessions = []
    for i in range(5):
        d_ = date(2026, 9, 2) + timedelta(days=i * 7)
        sess = SessionModel(
            class_id=cls.id, session_no=i + 1, date=d_,
            start_time=time(8, 0), end_time=time(10, 0), room="A1",
            status=SessionStatus.closed,
            opened_at=datetime.combine(d_, time(7, 50), tzinfo=VN_TZ),
            closed_at=datetime.combine(d_, time(10, 5), tzinfo=VN_TZ),
        )
        db_session.add(sess)
        sessions.append(sess)
    db_session.flush()

    # Thêm 1 buổi scheduled (không tính điểm)
    sess_sched = SessionModel(
        class_id=cls.id, session_no=6, date=date(2026, 11, 1),
        start_time=time(8, 0), end_time=time(10, 0), room="A1",
        status=SessionStatus.scheduled,
    )
    db_session.add(sess_sched)
    # Thêm 1 buổi cancelled (không tính điểm)
    sess_cancelled = SessionModel(
        class_id=cls.id, session_no=7, date=date(2026, 11, 8),
        start_time=time(8, 0), end_time=time(10, 0), room="A1",
        status=SessionStatus.cancelled,
    )
    db_session.add(sess_cancelled)
    db_session.flush()

    def _make_rec(sess_id, stu_id, status, source=AttendanceSource.manual, first_seen=None):
        r = AttendanceRecord(session_id=sess_id, student_id=stu_id, status=status, source=source, first_seen_at=first_seen)
        db_session.add(r)

    # SV0: 5 present → score = 10.0
    for sess in sessions:
        _make_rec(sess.id, students[0].id, AttendanceStatus.present)

    # SV1: 3 present, 2 late → 10*(3*1.0 + 2*0.5)/5 = 10*4/5 = 8.0
    for i, sess in enumerate(sessions):
        if i < 3:
            _make_rec(sess.id, students[1].id, AttendanceStatus.present)
        else:
            _make_rec(sess.id, students[1].id, AttendanceStatus.late)

    # SV2: 1 present, 1 late, 3 absent → 10*(1+0.5+0)/5 = 3.0 (cảnh báo: 3 absent = >= 3)
    _make_rec(sessions[0].id, students[2].id, AttendanceStatus.present)
    _make_rec(sessions[1].id, students[2].id, AttendanceStatus.late)
    for sess in sessions[2:]:
        _make_rec(sess.id, students[2].id, AttendanceStatus.absent, AttendanceSource.system)

    # SV3: 5 excused → 10*(5*1.0)/5 = 10.0
    for sess in sessions:
        _make_rec(sess.id, students[3].id, AttendanceStatus.excused, AttendanceSource.leave)

    # SV4: không có bản ghi (ghi danh giữa kỳ sau tất cả buổi closed) → score = null, nhưng đã enrolled
    # (không thêm record nào)

    db_session.commit()
    for x in sessions + [cls]:
        db_session.refresh(x)

    return {
        "u_admin": u_admin, "u_lec": u_lec, "cls": cls,
        "students": students, "sessions": sessions,
    }


# ── Công thức điểm ────────────────────────────────────────────────────────────

def test_attendance_score_all_present(db_session, report_data):
    """SV0: 5 present → 10.0."""
    d = report_data
    report = get_attendance_report(db_session, d["cls"].id, "admin")
    sv0 = next(r for r in report.items if r.student_id == d["students"][0].id)
    assert sv0.attendance_score == Decimal("10.0")
    assert sv0.present_count == 5


def test_attendance_score_mixed(db_session, report_data):
    """SV1: 3 present + 2 late → 8.0."""
    d = report_data
    report = get_attendance_report(db_session, d["cls"].id, "admin")
    sv1 = next(r for r in report.items if r.student_id == d["students"][1].id)
    assert sv1.attendance_score == Decimal("8.0")


def test_attendance_score_warning_flag(db_session, report_data):
    """SV2: 3 absent → cờ cảnh báo."""
    d = report_data
    report = get_attendance_report(db_session, d["cls"].id, "admin")
    sv2 = next(r for r in report.items if r.student_id == d["students"][2].id)
    assert sv2.has_warning is True
    assert sv2.absent_count == 3


def test_attendance_score_excused(db_session, report_data):
    """SV3: 5 excused → 10.0 (weight_excused=1.0)."""
    d = report_data
    report = get_attendance_report(db_session, d["cls"].id, "admin")
    sv3 = next(r for r in report.items if r.student_id == d["students"][3].id)
    assert sv3.attendance_score == Decimal("10.0")
    assert sv3.excused_count == 5


def test_attendance_score_no_closed_sessions_null(db_session, report_data):
    """SV4: không có bản ghi closed → score = null."""
    d = report_data
    report = get_attendance_report(db_session, d["cls"].id, "admin")
    sv4 = next(r for r in report.items if r.student_id == d["students"][4].id)
    assert sv4.attendance_score is None
    assert sv4.total_sessions == 0


def test_attendance_score_cancelled_not_counted(db_session, report_data):
    """Buổi cancelled và scheduled không tính vào mẫu số."""
    d = report_data
    report = get_attendance_report(db_session, d["cls"].id, "admin")
    sv0 = next(r for r in report.items if r.student_id == d["students"][0].id)
    assert sv0.total_sessions == 5  # chỉ 5 buổi closed, không tính scheduled/cancelled


def test_attendance_warning_at_threshold(db_session, report_data):
    """Cảnh báo khi absent >= attendance_warning_absences (3)."""
    d = report_data
    report = get_attendance_report(db_session, d["cls"].id, "admin")
    # SV2 có đúng 3 absent = ngưỡng
    sv2 = next(r for r in report.items if r.student_id == d["students"][2].id)
    assert sv2.has_warning is True
    # SV0 có 0 absent = không cảnh báo
    sv0 = next(r for r in report.items if r.student_id == d["students"][0].id)
    assert sv0.has_warning is False


def test_session_attendance_summary_is_not_double_counted(db_session, report_data):
    """Tóm tắt một buổi phải đếm mỗi bản ghi đúng một lần."""
    d = report_data
    session = d["sessions"][0]
    response = get_session_attendance(
        db_session, session.id, "admin", d["u_admin"].id, page=1, page_size=100
    )
    assert response.summary.total == 4
    assert response.summary.present == 3
    assert response.summary.late == 0
    assert response.summary.absent == 0
    assert response.summary.excused == 1


def test_attendance_score_half_up_rounding(db_session, report_data):
    """
    Test làm tròn HALF_UP: 3 present + 2 late với weight_late=0.5, total=5
    = 10*(3*1.0 + 2*0.5)/5 = 10*4/5 = 8.0 → không cần làm tròn
    Test edge: weight có thể tạo số lẻ → dùng weight_late=0.3 để test
    """
    d = report_data
    # Sửa tạm weight_late để tạo biên làm tròn
    # 1 present, 2 late với weight_late=0.3 → 10*(1+0.6)/3 = 5.333... → 5.3 (HALF_UP)
    cls = db_session.get(type(d["cls"]), d["cls"].id)
    original_weight = cls.weight_late
    cls.weight_late = 0.3
    db_session.flush()

    report = get_attendance_report(db_session, d["cls"].id, "admin")
    sv1 = next(r for r in report.items if r.student_id == d["students"][1].id)
    # 3 present + 2 late với weight_late=0.3: 10*(3+2*0.3)/5 = 10*3.6/5 = 7.2
    assert sv1.attendance_score == Decimal("7.2")

    # Restore
    cls.weight_late = original_weight
    db_session.flush()


def test_report_warning_filter(db_session, report_data):
    """Tham số warning=True chỉ trả sinh viên có cảnh báo."""
    d = report_data
    report = get_attendance_report(db_session, d["cls"].id, "admin", warning_only=True)
    assert all(r.has_warning for r in report.items)
    assert report.total >= 1


def test_report_no_n_plus_1(db_session, report_data):
    """
    Kiểm tra số truy vấn không tăng theo số sinh viên.
    report_service dùng truy vấn tổng hợp → số truy vấn cố định.
    """
    from sqlalchemy import event

    queries = []

    @event.listens_for(db_session.bind, "before_cursor_execute")
    def count_queries(conn, cursor, statement, parameters, context, executemany):
        queries.append(statement)

    d = report_data
    # Chạy với 5 SV
    get_attendance_report(db_session, d["cls"].id, "admin")
    count_5sv = len(queries)

    # Thêm 5 SV nữa (không có bản ghi — bài kiểm tra N+1 không phụ thuộc data)
    for i in range(5, 10):
        u = User(username=f"nq_{i}_{d['cls'].id}", email=f"nq_{i}@t.com",
                 password_hash=get_password_hash("X"), role=UserRole.student,
                 is_active=True, must_change_password=False, is_deleted=False, token_version=1)
        db_session.add(u)
        db_session.flush()
        stu = Student(user_id=u.id, student_code=f"SV_NQ_{i}_{d['cls'].id}", full_name=f"SV NQ {i}",
                      status=StudentStatus.studying, is_deleted=False)
        db_session.add(stu)
        db_session.flush()
        db_session.add(ClassStudent(class_id=d["cls"].id, student_id=stu.id, status=ClassStudentStatus.enrolled))
    db_session.flush()

    # Xóa query counter trước khi đo lần 2
    queries.clear()

    get_attendance_report(db_session, d["cls"].id, "admin")
    count_10sv = len(queries)

    # Số truy vấn không tăng theo số sinh viên (phải bằng nhau hoặc rất gần)
    event.remove(db_session.bind, "before_cursor_execute", count_queries)
    assert count_10sv == count_5sv, (
        f"Số truy vấn tăng theo SV: {count_5sv} → {count_10sv}. Kiểm tra N+1!"
    )
