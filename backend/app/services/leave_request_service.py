"""
services/leave_request_service.py
Đơn xin vắng: tạo, hủy, duyệt/từ chối.
"""

from __future__ import annotations

import logging
from datetime import UTC, timedelta

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app.core.config import settings
from app.models.attendance import (
    AttendanceRecord,
    AttendanceSource,
    AttendanceStatus,
    LeaveRequest,
    LeaveRequestStatus,
)
from app.models.class_ import ClassStudent, ClassStudentStatus
from app.models.learning import Notification
from app.models.session import Session as SessionModel
from app.models.session import SessionStatus
from app.models.student import Student
from app.models.user import User, UserRole
from app.schemas.leave_request import (
    LeaveRequestCreate,
    LeaveRequestListResponse,
    LeaveRequestOut,
    LeaveRequestReview,
)
from app.services.audit_service import log_action
from app.services.learning_access import ensure_class_writable
from app.utils.clock import VN_TZ, now_local

logger = logging.getLogger(__name__)

# Số ngày tối đa buổi đã qua vẫn được gửi đơn
LEAVE_REQUEST_PAST_DAYS = 7


def _get_session_or_404(db: Session, session_id: int) -> SessionModel:
    sess = db.get(SessionModel, session_id)
    if not sess:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "SESSION_NOT_FOUND", "message": "Không tìm thấy buổi học."},
        )
    return sess


def _get_leave_request_or_404(db: Session, request_id: int) -> LeaveRequest:
    req = db.execute(select(LeaveRequest).where(LeaveRequest.id == request_id)
                     .with_for_update().execution_options(populate_existing=True)).scalar_one_or_none()
    if not req:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "LEAVE_REQUEST_NOT_FOUND", "message": "Không tìm thấy đơn xin vắng."},
        )
    return req


def _require_class_lecturer_or_admin(db: Session, user: User, class_id: int) -> None:
    from app.models.class_ import Class
    from app.models.lecturer import Lecturer

    if user.role == UserRole.admin:
        return
    if user.role == UserRole.lecturer:
        lec = (
            db.query(Lecturer)
            .filter(Lecturer.user_id == user.id, Lecturer.is_deleted == False)
            .first()
        )
        cls = db.get(Class, class_id)
        if lec and cls and cls.lecturer_id == lec.id:
            return
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail={"code": "FORBIDDEN", "message": "Bạn không có quyền thực hiện thao tác này."},
    )


def _build_leave_out(req: LeaveRequest) -> LeaveRequestOut:
    out = LeaveRequestOut.model_validate(req)
    # Server-generated metadata is UTC; review timestamps use the shared VN clock.
    for field in ("created_at", "updated_at"):
        value = getattr(out, field)
        if value.tzinfo is None:
            setattr(out, field, value.replace(tzinfo=UTC))
    if out.reviewed_at is not None and out.reviewed_at.tzinfo is None:
        out.reviewed_at = out.reviewed_at.replace(tzinfo=VN_TZ)
    if req.student:
        out.student_name = req.student.full_name
        out.student_code = req.student.student_code
    if req.session:
        out.session_date = req.session.date
        out.class_id = req.session.class_id
        out.session_no = req.session.session_no
    if req.reviewer:
        out.reviewer_name = req.reviewer.username
    return out


# ─────────────────────────── public functions ────────────────────────────────


def create_leave_request(
    db: Session,
    student_id: int,
    data: LeaveRequestCreate,
    ip: str | None = None,
) -> LeaveRequestOut:
    """Sinh viên gửi đơn xin vắng."""
    sess = _get_session_or_404(db, data.session_id)
    ensure_class_writable(db, sess.class_id)
    # Serialize submissions for the same student so two requests cannot both
    # pass the pending check. No schema change or fake UI-only validation.
    db.execute(select(Student).where(Student.id == student_id).with_for_update())

    # Sinh viên phải enrolled
    cs = db.execute(
        select(ClassStudent).where(
            ClassStudent.class_id == sess.class_id,
            ClassStudent.student_id == student_id,
            ClassStudent.status == ClassStudentStatus.enrolled,
        )
    ).scalar_one_or_none()
    if not cs:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "NOT_ENROLLED", "message": "Bạn không thuộc lớp của buổi học này."},
        )

    # Kiểm tra ngày buổi học
    from app.utils.clock import now_local

    now = now_local()
    today = now.date()
    session_date = sess.date

    # Buổi phải scheduled hoặc đã qua trong LEAVE_REQUEST_PAST_DAYS ngày
    if sess.status == SessionStatus.cancelled:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "SESSION_CANCELLED", "message": "Không gửi đơn cho buổi đã hủy."},
        )

    if session_date < today:
        # Buổi quá khứ: phải trong 7 ngày
        days_ago = (today - session_date).days
        if days_ago > LEAVE_REQUEST_PAST_DAYS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "code": "SESSION_TOO_OLD",
                    "message": f"Chỉ gửi đơn cho buổi trong vòng {LEAVE_REQUEST_PAST_DAYS} ngày qua.",
                },
            )

    # Mỗi (sinh viên, buổi) chỉ một đơn pending
    existing_pending = db.execute(
        select(LeaveRequest).where(
            LeaveRequest.student_id == student_id,
            LeaveRequest.session_id == data.session_id,
            LeaveRequest.status == LeaveRequestStatus.pending,
        ).with_for_update().execution_options(populate_existing=True)
    ).scalar_one_or_none()
    if existing_pending:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "DUPLICATE_PENDING_REQUEST",
                "message": "Bạn đã có đơn xin vắng đang chờ duyệt cho buổi này.",
            },
        )

    req = LeaveRequest(
        student_id=student_id,
        session_id=data.session_id,
        reason=data.reason,
        status=LeaveRequestStatus.pending,
    )
    db.add(req)
    db.flush()

    student = db.get(Student, student_id)
    log_action(
        db=db,
        user_id=student.user_id if student else None,
        action="CREATE_LEAVE_REQUEST",
        entity="leave_requests",
        entity_id=str(req.id),
        detail={
            "session_id": data.session_id,
            "session_date": str(sess.date),
        },
        ip=ip,
    )
    db.commit()
    db.refresh(req)
    return _build_leave_out(req)


def cancel_leave_request(
    db: Session,
    request_id: int,
    student_id: int,
    actor_user_id: int,
    ip: str | None = None,
) -> LeaveRequestOut:
    """Sinh viên hủy đơn pending của mình."""
    req = _get_leave_request_or_404(db, request_id)

    if req.student_id != student_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "FORBIDDEN", "message": "Bạn không có quyền hủy đơn này."},
        )
    ensure_class_writable(db, req.session.class_id)
    if req.status != LeaveRequestStatus.pending:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "CANNOT_CANCEL",
                "message": f"Chỉ hủy được đơn đang pending. Trạng thái hiện tại: '{req.status.value}'.",
            },
        )

    req.status = LeaveRequestStatus.rejected  # hủy bởi sinh viên = rejected
    log_action(
        db=db,
        user_id=actor_user_id,
        action="CANCEL_LEAVE_REQUEST",
        entity="leave_requests",
        entity_id=str(req.id),
        detail={"session_id": req.session_id, "student_id": student_id},
        ip=ip,
    )
    db.commit()
    db.refresh(req)
    return _build_leave_out(req)


def review_leave_request(
    db: Session,
    request_id: int,
    reviewer: User,
    data: LeaveRequestReview,
    ip: str | None = None,
) -> LeaveRequestOut:
    """Duyệt hoặc từ chối đơn xin vắng."""
    req = _get_leave_request_or_404(db, request_id)
    sess = _get_session_or_404(db, req.session_id)

    _require_class_lecturer_or_admin(db, reviewer, sess.class_id)
    ensure_class_writable(db, sess.class_id)

    if req.status != LeaveRequestStatus.pending:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "ALREADY_REVIEWED",
                "message": f"Đơn đã được xử lý: '{req.status.value}'.",
            },
        )

    decision = data.decision
    now_ts = now_local()
    attendance_note = None

    if decision == "approve":
        # Kiểm tra cửa sổ sửa nếu buổi đã closed
        if (
            sess.status == SessionStatus.closed
            and reviewer.role != UserRole.admin
            and sess.closed_at
        ):
            closed_at = sess.closed_at
            if closed_at.tzinfo is None:
                closed_at = closed_at.replace(tzinfo=VN_TZ)
            deadline = closed_at + timedelta(hours=settings.EDIT_AFTER_CLOSE_HOURS)
            if now_ts > deadline:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail={
                        "code": "EDIT_WINDOW_EXPIRED",
                        "message": (
                            f"Cửa sổ sửa điểm danh ({settings.EDIT_AFTER_CLOSE_HOURS}h) đã hết. "
                            "Chỉ Admin mới có thể duyệt."
                        ),
                    },
                )

        req.status = LeaveRequestStatus.approved

        # Cập nhật bản ghi điểm danh nếu tồn tại và đang absent/system
        existing_rec = db.execute(
            select(AttendanceRecord).where(
                AttendanceRecord.session_id == sess.id,
                AttendanceRecord.student_id == req.student_id,
            )
        ).scalar_one_or_none()

        if existing_rec:
            if (
                existing_rec.status == AttendanceStatus.absent
                and existing_rec.source == AttendanceSource.system
            ):
                from app.models.attendance import AttendanceHistory

                old_status = existing_rec.status
                old_source = existing_rec.source
                existing_rec.status = AttendanceStatus.excused
                existing_rec.source = AttendanceSource.leave
                existing_rec.modified_by = reviewer.id
                existing_rec.modified_at = now_ts
                hist = AttendanceHistory(
                    record_id=existing_rec.id,
                    old_status=old_status,
                    new_status=AttendanceStatus.excused,
                    old_source=old_source,
                    new_source=AttendanceSource.leave,
                    note=f"Đơn xin vắng #{req.id} được duyệt",
                    changed_by=reviewer.id,
                    changed_at=now_ts,
                )
                db.add(hist)
            elif existing_rec.status in (AttendanceStatus.present, AttendanceStatus.late):
                attendance_note = "Sinh viên đã được điểm danh có mặt/trễ — không đổi trạng thái."
            else:
                attendance_note = (
                    f"Bản ghi điểm danh nguồn '{existing_rec.source.value}' — giữ nguyên."
                )

    else:  # reject
        req.status = LeaveRequestStatus.rejected

    req.reviewed_by = reviewer.id
    req.reviewed_at = now_ts
    req.review_note = data.review_note

    # M5: thông báo trong ứng dụng, được tạo cùng transaction với quyết định.
    student = db.get(Student, req.student_id)
    if student:
        decision_text = "được duyệt" if decision == "approve" else "bị từ chối"
        db.add(
            Notification(
                user_id=student.user_id,
                type="leave_request_reviewed",
                title="Đơn xin vắng đã được xử lý",
                body=f"Đơn xin vắng của bạn {decision_text}.",
                link=f"/student/classes/{sess.class_id}",
            )
        )

    log_action(
        db=db,
        user_id=reviewer.id,
        action="REVIEW_LEAVE_REQUEST",
        entity="leave_requests",
        entity_id=str(req.id),
        detail={
            "session_id": req.session_id,
            "student_id": req.student_id,
            "decision": decision,
            "attendance_note": attendance_note,
        },
        ip=ip,
    )
    db.commit()
    db.refresh(req)
    return _build_leave_out(req)


def get_leave_requests(
    db: Session,
    viewer: User,
    session_id: int | None = None,
    class_id: int | None = None,
    status_filter: LeaveRequestStatus | None = None,
    page: int = 1,
    page_size: int = 20,
) -> LeaveRequestListResponse:
    """Admin/Giảng viên xem danh sách đơn xin vắng."""
    from app.models.class_ import Class
    from app.models.lecturer import Lecturer
    from app.models.session import Session as SessionModel

    query = select(LeaveRequest).join(SessionModel, LeaveRequest.session_id == SessionModel.id)

    if viewer.role == UserRole.lecturer:
        # Lọc theo lớp mình dạy
        lec = (
            db.query(Lecturer)
            .filter(Lecturer.user_id == viewer.id, Lecturer.is_deleted == False)
            .first()
        )
        if not lec:
            return LeaveRequestListResponse(items=[], total=0, page=page, page_size=page_size)
        # join qua session -> class
        query = (
            query.join(Class, SessionModel.class_id == Class.id)
            .where(Class.lecturer_id == lec.id)
        )

    if session_id:
        query = query.where(LeaveRequest.session_id == session_id)
    if class_id:
        _require_class_lecturer_or_admin(db, viewer, class_id)
        query = query.where(SessionModel.class_id == class_id)
    if status_filter:
        query = query.where(LeaveRequest.status == status_filter)

    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0

    items_raw = (
        db.execute(
            query.options(joinedload(LeaveRequest.student), joinedload(LeaveRequest.session),
                          joinedload(LeaveRequest.reviewer)).order_by(LeaveRequest.created_at.desc(), LeaveRequest.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        .scalars()
        .all()
    )
    items = [_build_leave_out(r) for r in items_raw]
    return LeaveRequestListResponse(items=items, total=total, page=page, page_size=page_size)


def get_my_leave_requests(
    db: Session,
    student_id: int,
    page: int = 1,
    page_size: int = 20,
    class_id: int | None = None,
    status_filter: LeaveRequestStatus | None = None,
) -> LeaveRequestListResponse:
    """Sinh viên xem đơn của mình."""
    query = (
        select(LeaveRequest)
        .join(SessionModel, LeaveRequest.session_id == SessionModel.id)
        .where(LeaveRequest.student_id == student_id)
    )
    if class_id:
        enrollment = db.query(ClassStudent).filter(
            ClassStudent.class_id == class_id, ClassStudent.student_id == student_id,
            ClassStudent.status == ClassStudentStatus.enrolled,
        ).first()
        if not enrollment:
            raise HTTPException(403, detail={"code": "NOT_ENROLLED", "message": "Bạn không thuộc lớp học phần này."})
        query = query.where(SessionModel.class_id == class_id)
    if status_filter:
        query = query.where(LeaveRequest.status == status_filter)
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    items_raw = db.execute(query.options(
        joinedload(LeaveRequest.student), joinedload(LeaveRequest.session), joinedload(LeaveRequest.reviewer),
    ).order_by(LeaveRequest.created_at.desc(), LeaveRequest.id.desc())
        .offset((page - 1) * page_size).limit(page_size)).scalars().all()
    items = [_build_leave_out(r) for r in items_raw]
    return LeaveRequestListResponse(items=items, total=total, page=page, page_size=page_size)
