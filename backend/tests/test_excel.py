"""
test_excel.py
Kiểm tra xuất Excel: chống formula injection, cấu trúc 3 sheet, không lý do xin vắng.
"""

from __future__ import annotations

import io
import uuid
from datetime import date, datetime, time, timedelta

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
from app.services.excel_service import (
    _sanitize_cell,
    export_class_attendance,
    export_session_attendance,
)
from app.utils.clock import VN_TZ

_UID = lambda: uuid.uuid4().hex[:8]  # noqa: E731


def _make_user(db, role, uid, sfx=""):
    u = User(username=f"xl_{role.value}_{uid}{sfx}", email=f"xl_{role.value}_{uid}{sfx}@t.com",
             password_hash=get_password_hash("X"), role=role, is_active=True,
             must_change_password=False, is_deleted=False, token_version=1)
    db.add(u)
    db.flush()
    return u


@pytest.fixture
def excel_data(db_session):
    uid = _UID()
    sem = Semester(name=f"HK_XL_{uid}", start_date=date(2026, 9, 1), end_date=date(2026, 12, 31))
    db_session.add(sem)
    sub = Subject(code=f"XL_{uid}", name="Môn Excel", credits=3)
    db_session.add(sub)
    u_admin = _make_user(db_session, UserRole.admin, uid, "a")
    u_lec = _make_user(db_session, UserRole.lecturer, uid, "l")
    db_session.flush()
    lec = Lecturer(user_id=u_lec.id, code=f"XL_L_{uid}", full_name="GV", type=LecturerType.full_time, is_deleted=False)
    db_session.add(lec)
    db_session.flush()

    cls = Class(
        code=f"CLS_XL_{uid}", subject_id=sub.id, semester_id=sem.id,
        lecturer_id=lec.id, max_students=30, status=ClassStatus.active,
        late_after_min=10, absent_after_min=30,
        weight_present=1.0, weight_late=0.5, weight_excused=1.0,
        attendance_warning_absences=3,
        is_deleted=False,
    )
    db_session.add(cls)
    db_session.flush()

    # 3 sinh viên, tên có ký tự đặc biệt để test sanitize
    student_names = [
        "=Nguyễn Văn An",  # tên bắt đầu bằng = → phải sanitize
        "-Trần Thị Bình",   # bắt đầu bằng -
        "Lê Văn Cường",     # bình thường
    ]
    students = []
    for i, name in enumerate(student_names):
        u = _make_user(db_session, UserRole.student, uid, str(i))
        code = f"SV_XL_{uid}_{i}"
        stu = Student(user_id=u.id, student_code=code, full_name=name,
                      admin_class="K65-CNTT", status=StudentStatus.studying, is_deleted=False)
        db_session.add(stu)
        db_session.flush()
        db_session.add(ClassStudent(class_id=cls.id, student_id=stu.id, status=ClassStudentStatus.enrolled))
        students.append(stu)
    db_session.flush()

    # 2 buổi closed
    sessions = []
    for i in range(2):
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

    # Tạo bản ghi điểm danh
    for sess in sessions:
        for j, stu in enumerate(students):
            status = [AttendanceStatus.present, AttendanceStatus.late, AttendanceStatus.absent][j]
            db_session.add(AttendanceRecord(
                session_id=sess.id, student_id=stu.id,
                status=status, source=AttendanceSource.manual,
                note="=DANGEROUS_FORMULA" if j == 0 else None,  # test sanitize note
            ))
    db_session.flush()
    db_session.commit()

    for x in sessions + [cls]:
        db_session.refresh(x)

    return {
        "u_admin": u_admin, "cls": cls, "students": students, "sessions": sessions,
    }


# ── Sanitize ──────────────────────────────────────────────────────────────────

def test_sanitize_cell_equals():
    """Ô bắt đầu bằng = → thêm '."""
    assert _sanitize_cell("=SUM(A1)").startswith("'")


def test_sanitize_cell_minus():
    """Ô bắt đầu bằng - → thêm '."""
    assert _sanitize_cell("-1+1").startswith("'")


def test_sanitize_cell_plus():
    """Ô bắt đầu bằng + → thêm '."""
    assert _sanitize_cell("+1").startswith("'")


def test_sanitize_cell_at():
    """Ô bắt đầu bằng @ → thêm '."""
    assert _sanitize_cell("@USER").startswith("'")


def test_sanitize_cell_normal():
    """Ô bình thường → không đổi."""
    assert _sanitize_cell("Nguyễn Văn An") == "Nguyễn Văn An"


def test_sanitize_cell_none():
    """None → empty string."""
    assert _sanitize_cell(None) == ""


# ── Export session ────────────────────────────────────────────────────────────

def test_export_session_attendance_returns_bytes(db_session, excel_data):
    """export_session_attendance trả BytesIO hợp lệ."""
    d = excel_data
    buf = export_session_attendance(db_session, d["sessions"][0].id, d["u_admin"].id)
    assert isinstance(buf, io.BytesIO)
    assert buf.getbuffer().nbytes > 0


def test_export_session_attendance_sanitized_cells(db_session, excel_data):
    """Ô bắt đầu bằng = phải được sanitize trong file Excel."""
    import openpyxl

    d = excel_data
    buf = export_session_attendance(db_session, d["sessions"][0].id, d["u_admin"].id)
    wb = openpyxl.load_workbook(buf)
    ws = wb.active
    # Kiểm tra tất cả ô trong sheet
    for row in ws.iter_rows():
        for cell in row:
            val = str(cell.value or "")
            if val.startswith("="):
                pytest.fail(f"Ô chứa formula chưa được sanitize: {val!r}")


def test_export_session_attendance_no_reason(db_session, excel_data):
    """File xuất điểm danh không chứa lý do xin vắng."""
    import openpyxl

    d = excel_data
    buf = export_session_attendance(db_session, d["sessions"][0].id, d["u_admin"].id)
    wb = openpyxl.load_workbook(buf)
    all_values = [str(cell.value or "") for ws in wb.worksheets for row in ws.iter_rows() for cell in row]
    # Nếu có "reason" hay "lý do" field thì fail
    for val in all_values:
        assert "Đi khám" not in val
        assert "reason" not in val.lower()


# ── Export class (3 sheets) ───────────────────────────────────────────────────

def test_export_class_attendance_three_sheets(db_session, excel_data):
    """File xuất lớp có đúng 3 sheet."""
    import openpyxl

    d = excel_data
    buf = export_class_attendance(db_session, d["cls"].id, d["u_admin"].id)
    wb = openpyxl.load_workbook(buf)
    assert len(wb.sheetnames) == 3
    assert wb.sheetnames[0] == "Tổng hợp"
    assert wb.sheetnames[1] == "Chi tiết"
    assert wb.sheetnames[2] == "Chú thích"


def test_export_class_attendance_freeze_panes(db_session, excel_data):
    """Sheet Tổng hợp có freeze_panes."""
    import openpyxl

    d = excel_data
    buf = export_class_attendance(db_session, d["cls"].id, d["u_admin"].id)
    wb = openpyxl.load_workbook(buf)
    ws = wb["Tổng hợp"]
    assert ws.freeze_panes is not None


def test_export_class_attendance_sanitized_student_names(db_session, excel_data):
    """Tên sinh viên bắt đầu bằng = được sanitize trong sheet."""
    import openpyxl

    d = excel_data
    buf = export_class_attendance(db_session, d["cls"].id, d["u_admin"].id)
    wb = openpyxl.load_workbook(buf)
    for ws in wb.worksheets:
        for row in ws.iter_rows():
            for cell in row:
                val = str(cell.value or "")
                if val.startswith("="):
                    pytest.fail(f"Sheet '{ws.title}' có ô formula chưa sanitize: {val!r}")


def test_export_class_attendance_valid_openpyxl(db_session, excel_data):
    """File xuất mở được bằng openpyxl không lỗi."""
    import openpyxl

    d = excel_data
    buf = export_class_attendance(db_session, d["cls"].id, d["u_admin"].id)
    # Nếu file lỗi, load_workbook sẽ raise exception
    wb = openpyxl.load_workbook(buf)
    assert wb is not None
