"""
services/session_lifecycle_service.py
Vòng đời buổi học: mở, đóng, mở lại, tự đóng.
Mọi so sánh thời gian đi qua clock.now_local().
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.attendance import AttendanceRecord, AttendanceStatus
from app.models.class_ import Class, ClassStatus, ClassStudent, ClassStudentStatus
from app.models.learning import Notification
from app.models.session import Session as SessionModel
from app.models.session import SessionStatus
from app.models.user import User, UserRole
from app.schemas.session import SessionOut
from app.services.audit_service import log_action
from app.utils.clock import now_local

logger = logging.getLogger(__name__)


# ─────────────────────────────────────── helpers ────────────────────────────


def _get_session_or_404(db: Session, session_id: int) -> SessionModel:
    sess = db.get(SessionModel, session_id)
    if not sess:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "SESSION_NOT_FOUND", "message": "Không tìm thấy buổi học."},
        )
    return sess


def _get_class_or_404(db: Session, class_id: int) -> Class:
    cls = db.get(Class, class_id)
    if not cls or cls.is_deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "CLASS_NOT_FOUND", "message": "Không tìm thấy lớp học."},
        )
    return cls


def _require_admin_or_lecturer_of_class(db: Session, user: User, cls: Class) -> None:
    """Kiểm tra user là Admin hoặc giảng viên của lớp."""
    from app.models.lecturer import Lecturer

    if user.role == UserRole.admin:
        return
    if user.role == UserRole.lecturer:
        lec = (
            db.query(Lecturer)
            .filter(Lecturer.user_id == user.id, Lecturer.is_deleted == False)
            .first()
        )
        if lec and cls.lecturer_id == lec.id:
            return
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail={"code": "FORBIDDEN", "message": "Bạn không có quyền thực hiện thao tác này."},
    )


def _check_open_window(sess: SessionModel, user: User, reason: str | None) -> bool:
    """
    Kiểm tra cửa sổ giờ hợp lệ để mở buổi.
    Trả True nếu nằm trong cửa sổ.
    Admin ngoài cửa sổ: phải có lý do, ghi cảnh báo.
    Nếu DEV_ALLOW_OPEN_ANYTIME=True: luôn cho phép (ghi cảnh báo log+audit).
    Raise HTTPException nếu không đủ điều kiện.
    """
    now = now_local()
    # Kết hợp ngày và giờ của buổi học (giờ địa phương)
    from app.utils.clock import VN_TZ

    sess_start = datetime.combine(sess.date, sess.start_time).replace(tzinfo=VN_TZ)
    sess_end = datetime.combine(sess.date, sess.end_time).replace(tzinfo=VN_TZ)

    window_start = sess_start - timedelta(minutes=settings.SESSION_OPEN_BEFORE_MIN)
    window_end = sess_end + timedelta(minutes=settings.SESSION_OPEN_AFTER_END_MIN)

    in_window = window_start <= now <= window_end

    if settings.DEV_ALLOW_OPEN_ANYTIME:
        logger.warning(
            "[DEV_ALLOW_OPEN_ANYTIME] Mở buổi %s ngoài cửa sổ kiểm tra (now=%s, window=[%s, %s])",
            sess.id,
            now,
            window_start,
            window_end,
        )
        return True  # ghi audit bởi caller

    if not in_window:
        if user.role == UserRole.admin:
            if not reason:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail={
                        "code": "REASON_REQUIRED",
                        "message": (
                            "Admin mở buổi ngoài cửa sổ thời gian "
                            f"[{window_start.strftime('%H:%M')} – {window_end.strftime('%H:%M')}] "
                            "phải cung cấp lý do."
                        ),
                    },
                )
            return False  # ngoài cửa sổ, có lý do → cho phép
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "OUTSIDE_OPEN_WINDOW",
                "message": (
                    f"Chỉ có thể mở buổi trong khoảng [{window_start.strftime('%H:%M')} – "
                    f"{window_end.strftime('%H:%M')}]. Hiện tại: {now.strftime('%H:%M')}."
                ),
            },
        )
    return True


# ─────────────────────────────────── public API ─────────────────────────────


def open_session(
    db: Session,
    session_id: int,
    actor: User,
    reason: str | None = None,
    ip: str | None = None,
) -> SessionOut:
    """Mở buổi học (scheduled → open)."""
    sess = _get_session_or_404(db, session_id)
    cls = _get_class_or_404(db, sess.class_id)

    _require_admin_or_lecturer_of_class(db, actor, cls)

    # Lớp phải active
    if cls.status != ClassStatus.active:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "CLASS_NOT_ACTIVE", "message": "Lớp chưa ở trạng thái active."},
        )

    # Buổi phải scheduled
    if sess.status != SessionStatus.scheduled:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "INVALID_STATE_TRANSITION",
                "message": f"Không thể mở buổi ở trạng thái '{sess.status.value}'.",
            },
        )

    # Chỉ một buổi open trên mỗi lớp
    existing_open = db.execute(
        select(SessionModel)
        .where(
            SessionModel.class_id == sess.class_id,
            SessionModel.status == SessionStatus.open,
        )
        .limit(1)
    ).scalar_one_or_none()
    if existing_open and existing_open.id != sess.id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "SESSION_ALREADY_OPEN",
                "message": f"Lớp đang có buổi #{existing_open.session_no} đang mở. Đóng buổi đó trước.",
            },
        )

    in_window = _check_open_window(sess, actor, reason)
    now = now_local()

    # Ghi cảnh báo audit nếu DEV_ALLOW_OPEN_ANYTIME hoặc Admin ngoài cửa sổ
    extra_detail: dict = {}
    if settings.DEV_ALLOW_OPEN_ANYTIME:
        extra_detail["dev_allow_open_anytime"] = True
        extra_detail["warning"] = "DEV_ALLOW_OPEN_ANYTIME=True — chỉ dùng khi demo"
    elif not in_window and reason:
        extra_detail["outside_window"] = True
        extra_detail["reason"] = reason

    sess.status = SessionStatus.open
    sess.opened_at = now
    sess.opened_by = actor.id

    # Tạo bản ghi điểm danh (idempotent)
    from app.services.attendance_service import ensure_records

    ensure_records(db, sess)

    log_action(
        db=db,
        user_id=actor.id,
        action="OPEN_SESSION",
        entity="sessions",
        entity_id=str(sess.id),
        detail={
            "class_id": sess.class_id,
            "class_code": cls.code,
            "session_no": sess.session_no,
            "date": str(sess.date),
            **extra_detail,
        },
        ip=ip,
    )
    db.commit()
    db.refresh(sess)
    return SessionOut.model_validate(sess)


def close_session(
    db: Session,
    session_id: int,
    actor: User,
    ip: str | None = None,
) -> SessionOut:
    """Đóng buổi học (open → closed)."""
    sess = _get_session_or_404(db, session_id)
    cls = _get_class_or_404(db, sess.class_id)

    _require_admin_or_lecturer_of_class(db, actor, cls)

    if sess.status != SessionStatus.open:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "INVALID_STATE_TRANSITION",
                "message": f"Không thể đóng buổi ở trạng thái '{sess.status.value}'.",
            },
        )

    now = now_local()
    sess.status = SessionStatus.closed
    sess.closed_at = now
    sess.closed_by = actor.id

    _queue_attendance_warnings(db, cls)

    log_action(
        db=db,
        user_id=actor.id,
        action="CLOSE_SESSION",
        entity="sessions",
        entity_id=str(sess.id),
        detail={
            "class_id": sess.class_id,
            "class_code": cls.code,
            "session_no": sess.session_no,
            "date": str(sess.date),
        },
        ip=ip,
    )
    db.commit()
    db.refresh(sess)
    return SessionOut.model_validate(sess)


def _queue_attendance_warnings(db: Session, cls: Class) -> None:
    """M5: một thông báo duy nhất khi SV vừa đạt ngưỡng vắng của lớp."""
    from app.models.session import Session as SessionModel
    from app.models.student import Student

    threshold = cls.attendance_warning_absences
    rows = (
        db.query(Student)
        .join(ClassStudent, ClassStudent.student_id == Student.id)
        .filter(ClassStudent.class_id == cls.id, ClassStudent.status == ClassStudentStatus.enrolled)
        .all()
    )
    notification_type = f"attendance_warning:{cls.id}:{threshold}"
    for student in rows:
        absent_count = (
            db.query(AttendanceRecord)
            .join(SessionModel, SessionModel.id == AttendanceRecord.session_id)
            .filter(
                SessionModel.class_id == cls.id,
                SessionModel.status == SessionStatus.closed,
                AttendanceRecord.student_id == student.id,
                AttendanceRecord.status == AttendanceStatus.absent,
            )
            .count()
        )
        exists = (
            db.query(Notification.id)
            .filter(Notification.user_id == student.user_id, Notification.type == notification_type)
            .first()
        )
        if absent_count >= threshold and not exists:
            db.add(
                Notification(
                    user_id=student.user_id,
                    type=notification_type,
                    title="Cảnh báo chuyên cần",
                    body=f"Bạn đã vắng {absent_count} buổi, đạt ngưỡng cảnh báo của lớp {cls.code}.",
                    link=f"/student/classes/{cls.id}",
                )
            )


def reopen_session(
    db: Session,
    session_id: int,
    actor: User,
    reason: str,
    ip: str | None = None,
) -> SessionOut:
    """Mở lại buổi đã đóng — chỉ Admin."""
    if actor.role != UserRole.admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "FORBIDDEN", "message": "Chỉ Admin mới có thể mở lại buổi đã đóng."},
        )

    sess = _get_session_or_404(db, session_id)
    cls = _get_class_or_404(db, sess.class_id)

    if sess.status != SessionStatus.closed:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "INVALID_STATE_TRANSITION",
                "message": f"Chỉ có thể mở lại buổi đã đóng. Trạng thái hiện tại: '{sess.status.value}'.",
            },
        )

    existing_open = db.execute(
        select(SessionModel)
        .where(
            SessionModel.class_id == sess.class_id,
            SessionModel.status == SessionStatus.open,
            SessionModel.id != sess.id,
        )
        .limit(1)
    ).scalar_one_or_none()
    if existing_open:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "SESSION_ALREADY_OPEN",
                "message": f"Lớp đang có buổi #{existing_open.session_no} đang mở. Đóng buổi đó trước.",
            },
        )

    now = now_local()
    sess.status = SessionStatus.open
    sess.opened_at = now
    sess.opened_by = actor.id
    sess.closed_at = None
    sess.closed_by = None
    sess.auto_closed = False

    log_action(
        db=db,
        user_id=actor.id,
        action="REOPEN_SESSION",
        entity="sessions",
        entity_id=str(sess.id),
        detail={
            "class_id": sess.class_id,
            "class_code": cls.code,
            "session_no": sess.session_no,
            "date": str(sess.date),
            "reason": reason,
        },
        ip=ip,
    )
    db.commit()
    db.refresh(sess)
    return SessionOut.model_validate(sess)


def auto_close_overdue(db: Session) -> int:
    """
    Tự động đóng các buổi open quá SESSION_AUTO_CLOSE_AFTER_END_MIN kể từ giờ kết thúc.
    Được gọi bởi APScheduler mỗi phút VÀ bởi lazy check khi truy cập buổi.
    Trả về số buổi đã đóng.
    """
    from app.utils.clock import VN_TZ

    now = now_local()
    threshold_min = settings.SESSION_AUTO_CLOSE_AFTER_END_MIN

    open_sessions = (
        db.execute(select(SessionModel).where(SessionModel.status == SessionStatus.open))
        .scalars()
        .all()
    )

    closed_count = 0
    for sess in open_sessions:
        sess_end = datetime.combine(sess.date, sess.end_time).replace(tzinfo=VN_TZ)
        auto_close_time = sess_end + timedelta(minutes=threshold_min)
        if now >= auto_close_time:
            sess.status = SessionStatus.closed
            sess.closed_at = now
            sess.auto_closed = True
            # closed_by = None (hệ thống)
            log_action(
                db=db,
                user_id=None,
                action="AUTO_CLOSE_SESSION",
                entity="sessions",
                entity_id=str(sess.id),
                detail={
                    "class_id": sess.class_id,
                    "session_no": sess.session_no,
                    "date": str(sess.date),
                    "auto_close_threshold_min": threshold_min,
                },
                ip=None,
            )
            closed_count += 1

    if closed_count > 0:
        db.commit()
        logger.info("auto_close_overdue: đã đóng %d buổi.", closed_count)

    return closed_count


def lazy_auto_close(db: Session, sess: SessionModel) -> SessionModel:
    """
    Kiểm tra lười: nếu buổi open quá hạn thì đóng luôn.
    Gọi trước khi trả kết quả GET attendance hay khi mở buổi.
    """
    if sess.status != SessionStatus.open:
        return sess
    from app.utils.clock import VN_TZ

    now = now_local()
    sess_end = datetime.combine(sess.date, sess.end_time).replace(tzinfo=VN_TZ)
    auto_close_time = sess_end + timedelta(minutes=settings.SESSION_AUTO_CLOSE_AFTER_END_MIN)
    if now >= auto_close_time:
        sess.status = SessionStatus.closed
        sess.closed_at = now
        sess.auto_closed = True
        log_action(
            db=db,
            user_id=None,
            action="AUTO_CLOSE_SESSION",
            entity="sessions",
            entity_id=str(sess.id),
            detail={
                "class_id": sess.class_id,
                "session_no": sess.session_no,
                "date": str(sess.date),
                "trigger": "lazy_check",
            },
            ip=None,
        )
        db.commit()
        db.refresh(sess)
    return sess
