"""
routers/attendance.py
Điểm danh: xem, sửa, bulk, export, báo cáo, ma trận, my attendance.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db
from app.models.class_ import Class
from app.models.user import User, UserRole
from app.schemas.attendance import (
    AttendanceHistoryOut,
    AttendancePatch,
    BulkAttendancePatch,
    BulkAttendanceResult,
    MarkRemainingPatch,
    SessionAttendanceResponse,
)
from app.schemas.report import AttendanceMatrixResponse, AttendanceReportResponse
from app.services import attendance_service, excel_service, report_service
from app.utils.ip import get_client_ip

router = APIRouter(tags=["Attendance"])


def _require_admin_or_class_lecturer(db: Session, user: User, class_id: int) -> None:
    if user.role == UserRole.admin:
        return
    if user.role == UserRole.lecturer:
        from app.models.lecturer import Lecturer

        lec = db.query(Lecturer).filter(
            Lecturer.user_id == user.id, Lecturer.is_deleted == False
        ).first()
        cls = db.get(Class, class_id)
        if lec and cls and cls.lecturer_id == lec.id:
            return
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail={"code": "FORBIDDEN", "message": "Bạn không có quyền thực hiện thao tác này."},
    )


def _get_class_id_for_session(db: Session, session_id: int) -> int:
    from app.models.session import Session as SessionModel

    sess = db.get(SessionModel, session_id)
    if not sess:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "SESSION_NOT_FOUND", "message": "Không tìm thấy buổi học."},
        )
    return sess.class_id


# ──────────────────────── Session attendance ────────────────────────────────

@router.get("/sessions/{session_id}/attendance", response_model=SessionAttendanceResponse)
def get_session_attendance(
    session_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Danh sách điểm danh của một buổi, kèm tóm tắt."""
    class_id = _get_class_id_for_session(db, session_id)
    _require_admin_or_class_lecturer(db, current_user, class_id)
    return report_service.get_session_attendance(
        db, session_id, current_user.role.value, current_user.id, page, page_size
    )


@router.patch("/sessions/{session_id}/attendance/{student_id}", response_model=dict)
def patch_attendance(
    session_id: int,
    student_id: int,
    data: AttendancePatch,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Sửa thủ công trạng thái điểm danh."""
    class_id = _get_class_id_for_session(db, session_id)
    _require_admin_or_class_lecturer(db, current_user, class_id)
    rec = attendance_service.patch_attendance(
        db, session_id, student_id, data, current_user, get_client_ip(request)
    )
    return {"id": rec.id, "status": rec.status.value, "source": rec.source.value}


@router.get(
    "/sessions/{session_id}/attendance/{student_id}/history",
    response_model=list[AttendanceHistoryOut],
)
def get_attendance_history(
    session_id: int,
    student_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Lịch sử thay đổi điểm danh của một sinh viên trong một buổi."""
    class_id = _get_class_id_for_session(db, session_id)
    _require_admin_or_class_lecturer(db, current_user, class_id)
    history = attendance_service.get_attendance_history(db, session_id, student_id)
    return [
        AttendanceHistoryOut(
            id=h.id,
            record_id=h.record_id,
            old_status=h.old_status,
            new_status=h.new_status,
            old_source=h.old_source,
            new_source=h.new_source,
            note=h.note,
            changed_by=h.changed_by,
            changed_by_name=h.changer.username if h.changer else None,
            changed_at=h.changed_at,
        )
        for h in history
    ]


@router.post("/sessions/{session_id}/attendance/bulk", response_model=BulkAttendanceResult)
def bulk_patch_attendance(
    session_id: int,
    data: BulkAttendancePatch,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Sửa hàng loạt bản ghi điểm danh."""
    class_id = _get_class_id_for_session(db, session_id)
    _require_admin_or_class_lecturer(db, current_user, class_id)
    return attendance_service.bulk_patch_attendance(
        db, session_id, data, current_user, get_client_ip(request)
    )


@router.post("/sessions/{session_id}/attendance/mark-remaining", response_model=BulkAttendanceResult)
def mark_remaining_attendance(
    session_id: int,
    data: MarkRemainingPatch,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Áp trạng thái cho các bản ghi còn pending."""
    class_id = _get_class_id_for_session(db, session_id)
    _require_admin_or_class_lecturer(db, current_user, class_id)
    return attendance_service.mark_remaining_attendance(
        db, session_id, data, current_user, get_client_ip(request)
    )


@router.get("/sessions/{session_id}/attendance/export")
def export_session_attendance(
    session_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Xuất Excel điểm danh một buổi."""
    class_id = _get_class_id_for_session(db, session_id)
    _require_admin_or_class_lecturer(db, current_user, class_id)
    buf = excel_service.export_session_attendance(
        db, session_id, current_user.id, get_client_ip(request)
    )
    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename=diem-danh-buoi-{session_id}.xlsx"},
    )


# ──────────────────────── Class attendance ──────────────────────────────────

@router.get("/classes/{class_id}/attendance-report", response_model=AttendanceReportResponse)
def get_attendance_report(
    class_id: int,
    q: str | None = Query(None, description="Tìm theo tên/MSSV"),
    warning: bool = Query(False, description="Chỉ hiện sinh viên có cảnh báo"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Báo cáo chuyên cần toàn lớp."""
    _require_admin_or_class_lecturer(db, current_user, class_id)
    return report_service.get_attendance_report(
        db, class_id, current_user.role.value, q, warning, page, page_size
    )


@router.get("/classes/{class_id}/attendance-matrix", response_model=AttendanceMatrixResponse)
def get_attendance_matrix(
    class_id: int,
    student_id: int | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Ma trận điểm danh sinh viên × buổi (chỉ buổi closed)."""
    _require_admin_or_class_lecturer(db, current_user, class_id)
    return report_service.get_attendance_matrix(db, class_id, page, page_size, student_id)


@router.get("/classes/{class_id}/attendance/export")
def export_class_attendance(
    class_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Xuất Excel điểm danh lớp (3 sheet: Tổng hợp, Chi tiết, Chú thích)."""
    _require_admin_or_class_lecturer(db, current_user, class_id)
    buf = excel_service.export_class_attendance(
        db, class_id, current_user.id, get_client_ip(request)
    )
    cls = db.get(Class, class_id)
    filename = f"diem-danh-lop-{cls.code if cls else class_id}.xlsx"
    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


# ──────────────────────── My attendance (sinh viên) ─────────────────────────

@router.get("/me/attendance")
def get_my_attendance(
    class_id: int | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Sinh viên xem điểm danh của mình."""
    if current_user.role != UserRole.student:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "FORBIDDEN", "message": "Chỉ sinh viên mới có thể xem."},
        )
    from app.models.student import Student

    student = db.query(Student).filter(
        Student.user_id == current_user.id, Student.is_deleted == False
    ).first()
    if not student:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "STUDENT_NOT_FOUND", "message": "Không tìm thấy hồ sơ sinh viên."},
        )
    return report_service.get_my_attendance(db, student.id, class_id, page, page_size)
