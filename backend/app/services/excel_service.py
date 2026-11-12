"""
services/excel_service.py
Xuất Excel điểm danh (openpyxl, trong bộ nhớ, không ghi đĩa).
Chống formula injection; không chứa lý do xin vắng.
"""

from __future__ import annotations

import io
import logging
from datetime import date, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.attendance import AttendanceRecord, AttendanceStatus
from app.models.class_ import ClassStudent, ClassStudentStatus
from app.models.session import Session as SessionModel
from app.models.session import SessionStatus
from app.models.student import Student
from app.services.attendance_score import calculate_attendance_score
from app.services.audit_service import log_action
from app.utils.clock import now_local

logger = logging.getLogger(__name__)

# Ký hiệu hiển thị trong ma trận
STATUS_SYMBOL = {
    AttendanceStatus.present.value: "✓",
    AttendanceStatus.late.value: "L",
    AttendanceStatus.absent.value: "V",
    AttendanceStatus.excused.value: "P",
    None: "",
}

HEADER_FONT_SIZE = 11


def _sanitize_cell(value: str | None) -> str:
    """Chống formula injection: ô bắt đầu bằng = - + @ được thêm '."""
    if not value:
        return value or ""
    if isinstance(value, str) and value and value[0] in ("=", "-", "+", "@"):
        return "'" + value
    return value


def _fmt_date(d: date | None) -> str:
    if not d:
        return ""
    return d.strftime("%d/%m/%Y")


def _fmt_time(t) -> str:
    if not t:
        return ""
    return t.strftime("%H:%M")


def _fmt_dt(dt: datetime | None) -> str:
    if not dt:
        return ""
    return dt.strftime("%d/%m/%Y %H:%M")


def _status_label(status_val: str | None) -> str:
    labels = {
        "present": "Có mặt",
        "late": "Đi muộn",
        "absent": "Vắng",
        "excused": "Có phép",
    }
    return labels.get(status_val or "", "")


def _source_label(source_val: str | None) -> str:
    labels = {
        "face": "FaceID",
        "manual": "Thủ công",
        "leave": "Đơn phép",
        "system": "Hệ thống",
    }
    return labels.get(source_val or "", "")


def _make_workbook():
    try:
        import openpyxl
        from openpyxl.styles import Alignment, Font, PatternFill
    except ImportError:
        raise RuntimeError("openpyxl chưa được cài đặt.")
    return openpyxl, openpyxl.Workbook(), Font, PatternFill, Alignment


def _style_header_row(ws, row_idx: int, n_cols: int, openpyxl_mod, Font, PatternFill, Alignment):
    """Tô màu và in đậm hàng tiêu đề."""
    header_fill = PatternFill(start_color="4472C4", end_color="4472C4", fill_type="solid")
    for col in range(1, n_cols + 1):
        cell = ws.cell(row=row_idx, column=col)
        cell.font = Font(bold=True, color="FFFFFF", size=HEADER_FONT_SIZE)
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)


# ─────────────────────── export session attendance ───────────────────────────

def export_session_attendance(
    db: Session,
    session_id: int,
    actor_id: int,
    ip: str | None = None,
) -> io.BytesIO:
    """
    Xuất Excel điểm danh một buổi.
    Cột: MSSV, Họ tên, Lớp hành chính, Trạng thái, Giờ ghi nhận, Nguồn, Ghi chú.
    """
    openpyxl_mod, wb, Font, PatternFill, Alignment = _make_workbook()

    sess = db.get(SessionModel, session_id)
    if not sess:
        raise ValueError("Không tìm thấy buổi học.")

    ws = wb.active
    ws.title = "Điểm danh"

    # Metadata buổi
    ws.append([f"Buổi số {sess.session_no} — Ngày {_fmt_date(sess.date)} — {_fmt_time(sess.start_time)}–{_fmt_time(sess.end_time)} — Phòng {sess.room}"])
    ws.append([f"Trạng thái buổi: {sess.status.value}"])
    ws.append([])  # blank

    headers = ["MSSV", "Họ và tên", "Lớp HK", "Trạng thái", "Giờ ghi nhận", "Nguồn", "Ghi chú"]
    ws.append(headers)
    header_row = ws.max_row
    _style_header_row(ws, header_row, len(headers), openpyxl_mod, Font, PatternFill, Alignment)
    ws.freeze_panes = ws.cell(row=header_row + 1, column=1)

    # Dữ liệu
    rows = db.execute(
        select(
            AttendanceRecord,
            Student.student_code,
            Student.full_name,
            Student.admin_class,
        )
        .join(Student, AttendanceRecord.student_id == Student.id)
        .where(AttendanceRecord.session_id == session_id)
        .order_by(Student.student_code)
    ).all()

    for rec, student_code, full_name, admin_class in rows:
        ws.append([
            _sanitize_cell(student_code),
            _sanitize_cell(full_name),
            _sanitize_cell(admin_class or ""),
            _status_label(rec.status.value),
            _fmt_dt(rec.first_seen_at),
            _source_label(rec.source.value),
            _sanitize_cell(rec.note or ""),
        ])

    # Độ rộng cột
    col_widths = [15, 30, 15, 14, 20, 14, 30]
    for i, w in enumerate(col_widths, start=1):
        ws.column_dimensions[openpyxl_mod.utils.get_column_letter(i)].width = w

    log_action(
        db=db,
        user_id=actor_id,
        action="EXPORT_SESSION_ATTENDANCE",
        entity="sessions",
        entity_id=str(session_id),
        detail={"session_no": sess.session_no, "class_id": sess.class_id},
        ip=ip,
    )
    db.commit()

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf


# ─────────────────────── export class attendance ─────────────────────────────

def export_class_attendance(
    db: Session,
    class_id: int,
    actor_id: int,
    ip: str | None = None,
) -> io.BytesIO:
    """
    Xuất Excel điểm danh lớp (3 sheet):
    - Sheet "Tổng hợp": một dòng/sinh viên, số liệu chuyên cần
    - Sheet "Chi tiết": ma trận sinh viên × buổi
    - Sheet "Chú thích": ý nghĩa ký hiệu
    Không chứa lý do xin vắng.
    """
    from app.models.class_ import Class

    openpyxl_mod, wb, Font, PatternFill, Alignment = _make_workbook()

    cls = db.get(Class, class_id)
    if not cls:
        raise ValueError("Không tìm thấy lớp.")

    # Buổi closed
    closed_sessions = db.execute(
        select(SessionModel)
        .where(SessionModel.class_id == class_id, SessionModel.status == SessionStatus.closed)
        .order_by(SessionModel.date.asc(), SessionModel.start_time.asc())
    ).scalars().all()

    # Sinh viên
    students = db.execute(
        select(
            ClassStudent.student_id,
            ClassStudent.status.label("cs_status"),
            Student.student_code,
            Student.full_name,
            Student.admin_class,
        )
        .join(Student, ClassStudent.student_id == Student.id)
        .where(ClassStudent.class_id == class_id)
        .order_by(Student.student_code)
    ).all()

    # Map điểm danh
    all_recs = {}
    if closed_sessions:
        recs = db.execute(
            select(AttendanceRecord).where(
                AttendanceRecord.session_id.in_([s.id for s in closed_sessions])
            )
        ).scalars().all()
        for r in recs:
            all_recs[(r.session_id, r.student_id)] = r

    # ── Sheet 1: Tổng hợp ──────────────────────────────────────────────────
    ws1 = wb.active
    ws1.title = "Tổng hợp"
    ws1.append([f"Lớp: {cls.code} — Xuất ngày {_fmt_date(now_local().date())}"])
    ws1.append([])
    h1 = ["MSSV", "Họ và tên", "Lớp HK", "Tổng buổi", "Có mặt", "Đi muộn", "Vắng", "Có phép", "Điểm CC", "Cảnh báo", "Trạng thái"]
    ws1.append(h1)
    _style_header_row(ws1, ws1.max_row, len(h1), openpyxl_mod, Font, PatternFill, Alignment)
    ws1.freeze_panes = "A4"

    for s in students:
        total = present = late = absent = excused = 0
        for sess in closed_sessions:
            rec = all_recs.get((sess.id, s.student_id))
            if rec:
                total += 1
                if rec.status == AttendanceStatus.present:
                    present += 1
                elif rec.status == AttendanceStatus.late:
                    late += 1
                elif rec.status == AttendanceStatus.absent:
                    absent += 1
                elif rec.status == AttendanceStatus.excused:
                    excused += 1

        attendance_score = calculate_attendance_score(
            present_count=present,
            late_count=late,
            excused_count=excused,
            total_count=total,
            weight_present=cls.weight_present,
            weight_late=cls.weight_late,
            weight_excused=cls.weight_excused,
        )
        score = float(attendance_score) if attendance_score is not None else ""

        has_warning = absent >= cls.attendance_warning_absences
        cs_status = "Đã rút" if s.cs_status == ClassStudentStatus.dropped else "Đang học"

        ws1.append([
            _sanitize_cell(s.student_code),
            _sanitize_cell(s.full_name),
            _sanitize_cell(s.admin_class or ""),
            total,
            present,
            late,
            absent,
            excused,
            score,
            "⚠️ Cảnh báo" if has_warning else "",
            cs_status,
        ])

    for i, w in enumerate([15, 30, 15, 10, 10, 10, 8, 10, 10, 14, 12], start=1):
        ws1.column_dimensions[openpyxl_mod.utils.get_column_letter(i)].width = w

    # ── Sheet 2: Chi tiết (ma trận) ────────────────────────────────────────
    ws2 = wb.create_sheet("Chi tiết")
    # Header hàng 1: thông tin buổi
    date_row = ["MSSV", "Họ và tên"] + [_fmt_date(s.date) for s in closed_sessions]
    ws2.append(date_row)
    no_row = ["", ""] + [f"Buổi {s.session_no}" for s in closed_sessions]
    ws2.append(no_row)
    _style_header_row(ws2, 1, len(date_row), openpyxl_mod, Font, PatternFill, Alignment)
    _style_header_row(ws2, 2, len(date_row), openpyxl_mod, Font, PatternFill, Alignment)
    ws2.freeze_panes = "C3"

    for s in students:
        cells = [_sanitize_cell(s.student_code), _sanitize_cell(s.full_name)]
        for sess in closed_sessions:
            rec = all_recs.get((sess.id, s.student_id))
            cells.append(STATUS_SYMBOL.get(rec.status.value if rec else None, ""))
        ws2.append(cells)

    ws2.column_dimensions["A"].width = 15
    ws2.column_dimensions["B"].width = 30
    for i in range(3, 3 + len(closed_sessions)):
        ws2.column_dimensions[openpyxl_mod.utils.get_column_letter(i)].width = 10

    # ── Sheet 3: Chú thích ────────────────────────────────────────────────
    ws3 = wb.create_sheet("Chú thích")
    ws3.append(["Ký hiệu", "Ý nghĩa"])
    _style_header_row(ws3, 1, 2, openpyxl_mod, Font, PatternFill, Alignment)
    ws3.append(["✓", "Có mặt (Present)"])
    ws3.append(["L", "Đi muộn (Late)"])
    ws3.append(["V", "Vắng (Absent)"])
    ws3.append(["P", "Có phép (Excused)"])
    ws3.append(["", "Không có bản ghi"])
    ws3.append([])
    ws3.append(["Nguồn", "Ý nghĩa"])
    _style_header_row(ws3, ws3.max_row, 2, openpyxl_mod, Font, PatternFill, Alignment)
    ws3.append(["FaceID", "Nhận diện khuôn mặt"])
    ws3.append(["Thủ công", "Giảng viên điểm danh/sửa thủ công"])
    ws3.append(["Đơn phép", "Có đơn xin vắng được duyệt"])
    ws3.append(["Hệ thống", "Mặc định khi mở buổi"])
    ws3.column_dimensions["A"].width = 14
    ws3.column_dimensions["B"].width = 35

    log_action(
        db=db,
        user_id=actor_id,
        action="EXPORT_CLASS_ATTENDANCE",
        entity="classes",
        entity_id=str(class_id),
        detail={"class_code": cls.code, "n_sessions": len(closed_sessions)},
        ip=ip,
    )
    db.commit()

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf
