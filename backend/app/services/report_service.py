"""
services/report_service.py
Báo cáo chuyên cần: tổng hợp điểm, ma trận, my attendance.
Dùng truy vấn tổng hợp — không N+1.
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import and_, case, func, select
from sqlalchemy.orm import Session

from app.models.attendance import AttendanceRecord, AttendanceSource, AttendanceStatus
from app.models.class_ import Class, ClassStudent, ClassStudentStatus
from app.models.session import Session as SessionModel
from app.models.session import SessionStatus
from app.models.student import Student
from app.schemas.report import (
    AttendanceMatrixCell,
    AttendanceMatrixResponse,
    AttendanceMatrixRow,
    AttendanceReportResponse,
    MyAttendanceRecord,
    MyAttendanceResponse,
    MyAttendanceSummary,
    StudentAttendanceSummary,
)
from app.services.attendance_score import calculate_attendance_score

logger = logging.getLogger(__name__)


def _compute_display_status(rec: AttendanceRecord, session_status: str) -> str:
    if (
        rec.status == AttendanceStatus.absent
        and rec.source == AttendanceSource.system
        and session_status == SessionStatus.open.value
    ):
        return "pending"
    return rec.status.value


def _can_edit(session_status: str, actor_role: str, closed_at: Any, edit_hours: int) -> bool:
    """Kiểm tra người đang xem có thể sửa không."""
    from datetime import timedelta

    from app.utils.clock import now_local

    if session_status == SessionStatus.open.value:
        return True
    if session_status == SessionStatus.closed.value:
        if actor_role == "admin":
            return True
        if closed_at:
            if getattr(closed_at, "tzinfo", None) is None:
                from app.utils.clock import VN_TZ
                closed_at = closed_at.replace(tzinfo=VN_TZ)
            deadline = closed_at + timedelta(hours=edit_hours)
            return now_local() <= deadline
    return False


# ─────────────────────── attendance report (per class) ──────────────────────

def get_attendance_report(
    db: Session,
    class_id: int,
    actor_role: str,
    q: str | None = None,
    warning_only: bool = False,
    page: int = 1,
    page_size: int = 20,
) -> AttendanceReportResponse:
    """
    Tổng hợp chuyên cần cho từng sinh viên trong lớp.
    Chỉ tính buổi closed không hủy.
    Dùng một truy vấn tổng hợp — O(1) truy vấn.
    """
    cls = db.get(Class, class_id)
    if not cls:
        from fastapi import HTTPException
        from fastapi import status as http_status
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"code": "CLASS_NOT_FOUND", "message": "Không tìm thấy lớp."},
        )

    # Buổi closed không hủy
    closed_session_ids_q = select(SessionModel.id).where(
        SessionModel.class_id == class_id,
        SessionModel.status == SessionStatus.closed,
    )

    # Tổng hợp điểm danh theo sinh viên — một truy vấn GROUP BY
    agg_stmt = (
        select(
            AttendanceRecord.student_id,
            func.count(AttendanceRecord.id).label("total"),
            func.sum(
                case(
                    (AttendanceRecord.status == AttendanceStatus.present, 1),
                    else_=0,
                )
            ).label("present_count"),
            func.sum(
                case(
                    (AttendanceRecord.status == AttendanceStatus.late, 1),
                    else_=0,
                )
            ).label("late_count"),
            func.sum(
                case(
                    (AttendanceRecord.status == AttendanceStatus.absent, 1),
                    else_=0,
                )
            ).label("absent_count"),
            func.sum(
                case(
                    (AttendanceRecord.status == AttendanceStatus.excused, 1),
                    else_=0,
                )
            ).label("excused_count"),
        )
        .where(AttendanceRecord.session_id.in_(closed_session_ids_q))
        .group_by(AttendanceRecord.student_id)
    )

    # Sinh viên trong lớp
    student_q = (
        select(
            ClassStudent.student_id,
            ClassStudent.status.label("cs_status"),
            Student.student_code,
            Student.full_name,
            Student.admin_class,
        )
        .join(Student, ClassStudent.student_id == Student.id)
        .where(ClassStudent.class_id == class_id)
    )
    if q:
        like = f"%{q}%"
        student_q = student_q.where(
            Student.full_name.ilike(like) | Student.student_code.ilike(like)
        )

    student_rows = db.execute(student_q).all()

    # Map tổng hợp
    agg_rows = {r.student_id: r for r in db.execute(agg_stmt).all()}

    results: list[StudentAttendanceSummary] = []
    for row in student_rows:
        agg_row = agg_rows.get(row.student_id)
        total = agg_row.total if agg_row else 0
        present_count = agg_row.present_count if agg_row else 0
        late_count = agg_row.late_count if agg_row else 0
        absent_count = agg_row.absent_count if agg_row else 0
        excused_count = agg_row.excused_count if agg_row else 0

        # Tính điểm chuyên cần
        attendance_score = calculate_attendance_score(
            present_count=present_count,
            late_count=late_count,
            excused_count=excused_count,
            total_count=total,
            weight_present=cls.weight_present,
            weight_late=cls.weight_late,
            weight_excused=cls.weight_excused,
        )
        attendance_rate = (present_count + late_count) / total if total > 0 else None

        has_warning = absent_count >= cls.attendance_warning_absences
        is_dropped = row.cs_status == ClassStudentStatus.dropped

        summary = StudentAttendanceSummary(
            student_id=row.student_id,
            student_code=row.student_code,
            full_name=row.full_name,
            admin_class=row.admin_class,
            is_dropped=is_dropped,
            total_sessions=total,
            present_count=present_count,
            late_count=late_count,
            absent_count=absent_count,
            excused_count=excused_count,
            attendance_rate=attendance_rate,
            attendance_score=attendance_score,
            has_warning=has_warning,
        )
        results.append(summary)

    if warning_only:
        results = [r for r in results if r.has_warning]

    total_items = len(results)
    paginated = results[(page - 1) * page_size : page * page_size]

    return AttendanceReportResponse(
        items=paginated,
        total=total_items,
        page=page,
        page_size=page_size,
    )


# ──────────────────────── attendance matrix ──────────────────────────────────

def get_attendance_matrix(
    db: Session,
    class_id: int,
    page: int = 1,
    page_size: int = 20,
    student_id: int | None = None,
) -> AttendanceMatrixResponse:
    """Ma trận sinh viên × buổi (closed)."""
    cls = db.get(Class, class_id)
    if not cls:
        from fastapi import HTTPException
        from fastapi import status as http_status
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"code": "CLASS_NOT_FOUND", "message": "Không tìm thấy lớp."},
        )

    # Lấy buổi closed theo thứ tự
    closed_sessions = (
        db.execute(
            select(SessionModel)
            .where(
                SessionModel.class_id == class_id,
                SessionModel.status == SessionStatus.closed,
            )
            .order_by(SessionModel.date.asc(), SessionModel.start_time.asc())
        )
        .scalars()
        .all()
    )
    session_ids = [s.id for s in closed_sessions]
    session_meta = [
        {
            "id": s.id,
            "session_no": s.session_no,
            "date": str(s.date),
            "start_time": str(s.start_time),
        }
        for s in closed_sessions
    ]

    # Sinh viên
    students_q = (
        select(
            ClassStudent.student_id,
            ClassStudent.status.label("cs_status"),
            Student.student_code,
            Student.full_name,
        )
        .join(Student, ClassStudent.student_id == Student.id)
        .where(ClassStudent.class_id == class_id)
        .order_by(Student.student_code)
    )
    if student_id is not None:
        students_q = students_q.where(ClassStudent.student_id == student_id)
    all_students = db.execute(students_q).all()
    total = len(all_students)
    paginated_students = all_students[(page - 1) * page_size : page * page_size]
    student_ids = [r.student_id for r in paginated_students]

    # Lấy tất cả bản ghi điểm danh cho student_ids × session_ids
    if session_ids and student_ids:
        records = db.execute(
            select(AttendanceRecord).where(
                AttendanceRecord.session_id.in_(session_ids),
                AttendanceRecord.student_id.in_(student_ids),
            )
        ).scalars().all()
        rec_map = {(r.session_id, r.student_id): r.status.value for r in records}
    else:
        rec_map = {}

    rows: list[AttendanceMatrixRow] = []
    for sr in paginated_students:
        cells = [
            AttendanceMatrixCell(status=rec_map.get((sid, sr.student_id)))
            for sid in session_ids
        ]
        rows.append(
            AttendanceMatrixRow(
                student_id=sr.student_id,
                student_code=sr.student_code,
                full_name=sr.full_name,
                is_dropped=sr.cs_status == ClassStudentStatus.dropped,
                cells=cells,
            )
        )

    return AttendanceMatrixResponse(
        sessions=session_meta,
        items=rows,
        total=total,
        page=page,
        page_size=page_size,
    )


# ──────────────────────── session attendance detail ──────────────────────────

def get_session_attendance(
    db: Session,
    session_id: int,
    actor_role: str,
    actor_user_id: int,
    page: int = 1,
    page_size: int = 100,
) -> dict:
    """GET /sessions/{id}/attendance — danh sách bản ghi kèm tóm tắt."""
    from app.core.config import settings as cfg

    sess = db.get(SessionModel, session_id)
    if not sess:
        from fastapi import HTTPException
        from fastapi import status as http_status
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"code": "SESSION_NOT_FOUND", "message": "Không tìm thấy buổi học."},
        )

    # Lazy auto close
    from app.services.session_lifecycle_service import lazy_auto_close
    sess = lazy_auto_close(db, sess)

    # ensure_records để bù sinh viên ghi danh sau khi mở
    if sess.status == SessionStatus.open:
        from app.services.attendance_service import ensure_records
        ensure_records(db, sess)

    # Lấy bản ghi kèm thông tin sinh viên
    recs_q = (
        select(
            AttendanceRecord,
            ClassStudent.status.label("cs_status"),
            Student.student_code,
            Student.full_name,
            Student.admin_class,
        )
        .join(Student, AttendanceRecord.student_id == Student.id)
        .join(
            ClassStudent,
            and_(
                ClassStudent.class_id == sess.class_id,
                ClassStudent.student_id == AttendanceRecord.student_id,
            ),
        )
        .where(AttendanceRecord.session_id == session_id)
        .order_by(Student.student_code)
    )

    all_rows = db.execute(recs_q).all()
    total = len(all_rows)
    paginated = all_rows[(page - 1) * page_size : page * page_size]

    from app.schemas.attendance import (
        AttendanceRecordOut,
        AttendanceSummary,
        SessionAttendanceResponse,
    )

    summary = AttendanceSummary()
    items = []
    for row in all_rows:
        rec = row[0]
        disp = _compute_display_status(rec, sess.status.value)
        if disp == "pending":
            summary.pending += 1
        if rec.status == AttendanceStatus.present:
            summary.present += 1
        elif rec.status == AttendanceStatus.late:
            summary.late += 1
        elif rec.status == AttendanceStatus.absent:
            summary.absent += 1
        elif rec.status == AttendanceStatus.excused:
            summary.excused += 1
        summary.total += 1

    for row in paginated:
        rec = row[0]
        cs_status = row[1]
        disp = _compute_display_status(rec, sess.status.value)
        items.append(
            AttendanceRecordOut(
                id=rec.id,
                session_id=rec.session_id,
                student_id=rec.student_id,
                student_code=row[2],
                full_name=row[3],
                admin_class=row[4],
                status=rec.status,
                source=rec.source,
                display_status=disp,
                first_seen_at=rec.first_seen_at,
                hit_count=rec.hit_count,
                confidence=rec.confidence,
                note=rec.note,
                modified_by=rec.modified_by,
                modified_at=rec.modified_at,
                is_dropped=(cs_status == ClassStudentStatus.dropped),
            )
        )

    can_edit_flag = _can_edit(
        sess.status.value,
        actor_role,
        sess.closed_at,
        cfg.EDIT_AFTER_CLOSE_HOURS,
    )

    return SessionAttendanceResponse(
        session_id=session_id,
        session_status=sess.status.value,
        can_edit=can_edit_flag,
        summary=summary,
        items=items,
        total=total,
        page=page,
        page_size=page_size,
    )


# ──────────────────────── my attendance (sinh viên) ─────────────────────────

def get_my_attendance(
    db: Session,
    student_id: int,
    class_id: int | None = None,
    page: int = 1,
    page_size: int = 50,
) -> list[MyAttendanceResponse]:
    """Sinh viên xem điểm danh của mình. Trả danh sách theo lớp."""
    # Lớp đang ghi danh
    cs_query = select(ClassStudent).where(
        ClassStudent.student_id == student_id,
    )
    if class_id:
        cs_query = cs_query.where(ClassStudent.class_id == class_id)
    class_students = db.execute(cs_query).scalars().all()

    result = []
    for cs in class_students:
        cls = db.get(Class, cs.class_id)
        if not cls:
            continue

        # Tổng hợp cho lớp này
        closed_session_ids_q = select(SessionModel.id).where(
            SessionModel.class_id == cs.class_id,
            SessionModel.status == SessionStatus.closed,
        )
        agg = db.execute(
            select(
                func.count(AttendanceRecord.id).label("total"),
                func.sum(case((AttendanceRecord.status == AttendanceStatus.present, 1), else_=0)).label("present"),
                func.sum(case((AttendanceRecord.status == AttendanceStatus.late, 1), else_=0)).label("late"),
                func.sum(case((AttendanceRecord.status == AttendanceStatus.absent, 1), else_=0)).label("absent"),
                func.sum(case((AttendanceRecord.status == AttendanceStatus.excused, 1), else_=0)).label("excused"),
            ).where(
                AttendanceRecord.student_id == student_id,
                AttendanceRecord.session_id.in_(closed_session_ids_q),
            )
        ).first()

        total = agg.total or 0
        present = agg.present or 0
        late = agg.late or 0
        absent = agg.absent or 0
        excused = agg.excused or 0

        attendance_score = calculate_attendance_score(
            present_count=present,
            late_count=late,
            excused_count=excused,
            total_count=total,
            weight_present=cls.weight_present,
            weight_late=cls.weight_late,
            weight_excused=cls.weight_excused,
        )

        has_warning = absent >= cls.attendance_warning_absences

        summary = MyAttendanceSummary(
            class_id=cs.class_id,
            class_code=cls.code,
            subject_name=cls.subject.name if cls.subject else None,
            attendance_score=attendance_score,
            total_sessions=total,
            present_count=present,
            late_count=late,
            absent_count=absent,
            excused_count=excused,
            has_warning=has_warning,
            warning_threshold=cls.attendance_warning_absences,
        )

        # Các bản ghi của sinh viên
        recs = db.execute(
            select(AttendanceRecord, SessionModel)
            .join(SessionModel, AttendanceRecord.session_id == SessionModel.id)
            .where(
                AttendanceRecord.student_id == student_id,
                SessionModel.class_id == cs.class_id,
            )
            .order_by(SessionModel.date.asc(), SessionModel.start_time.asc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        ).all()

        records_out = []
        for rec, sess in recs:
            disp = _compute_display_status(rec, sess.status.value)
            records_out.append(
                MyAttendanceRecord(
                    session_id=sess.id,
                    session_no=sess.session_no,
                    date=sess.date,
                    start_time=sess.start_time,
                    end_time=sess.end_time,
                    room=sess.room,
                    session_status=sess.status.value,
                    status=rec.status.value,
                    display_status=disp,
                    source=rec.source.value,
                    first_seen_at=rec.first_seen_at,
                    note=rec.note,
                )
            )

        result.append(MyAttendanceResponse(
            summary=summary,
            records=records_out,
            total=total,
        ))

    return result
