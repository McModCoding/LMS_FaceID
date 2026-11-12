"""
services/attendance_service.py
Logic điểm danh: ensure_records, apply_presence, patch, bulk, history.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from math import isfinite
from typing import Literal

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.attendance import (
    AttendanceHistory,
    AttendanceRecord,
    AttendanceSource,
    AttendanceStatus,
    LeaveRequest,
    LeaveRequestStatus,
)
from app.models.class_ import ClassStudent, ClassStudentStatus
from app.models.session import Session as SessionModel
from app.models.session import SessionStatus
from app.models.user import User, UserRole
from app.schemas.attendance import (
    AttendancePatch,
    BulkAttendancePatch,
    BulkAttendanceResult,
    CheckInResult,
    MarkRemainingPatch,
)
from app.services.audit_service import log_action
from app.utils.clock import VN_TZ, now_local

logger = logging.getLogger(__name__)


# ────────────────────────────────────── helpers ──────────────────────────────

def _get_session_or_404(db: Session, session_id: int) -> SessionModel:
    sess = db.get(SessionModel, session_id)
    if not sess:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "SESSION_NOT_FOUND", "message": "Không tìm thấy buổi học."},
        )
    return sess


def _get_record_or_404(db: Session, session_id: int, student_id: int) -> AttendanceRecord:
    rec = db.execute(
        select(AttendanceRecord).where(
            AttendanceRecord.session_id == session_id,
            AttendanceRecord.student_id == student_id,
        )
    ).scalar_one_or_none()
    if not rec:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "RECORD_NOT_FOUND", "message": "Không tìm thấy bản ghi điểm danh."},
        )
    return rec


def _require_class_lecturer_or_admin(db: Session, user: User, class_id: int) -> None:
    from app.models.class_ import Class
    from app.models.lecturer import Lecturer

    if user.role == UserRole.admin:
        return
    if user.role == UserRole.lecturer:
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


def _check_edit_permission(db: Session, sess: SessionModel, actor: User) -> None:
    """
    Kiểm tra quyền sửa điểm danh sau khi buổi đóng.
    - Admin: luôn được
    - Giảng viên: chỉ trong EDIT_AFTER_CLOSE_HOURS kể từ closed_at, phải có note
    """
    if sess.status == SessionStatus.closed and actor.role != UserRole.admin:
        if not sess.closed_at:
            return
        closed_at = sess.closed_at
        if closed_at.tzinfo is None:
            closed_at = closed_at.replace(tzinfo=VN_TZ)
        deadline = closed_at + timedelta(hours=settings.EDIT_AFTER_CLOSE_HOURS)
        if now_local() > deadline:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "code": "EDIT_WINDOW_EXPIRED",
                    "message": (
                        f"Cửa sổ sửa điểm danh ({settings.EDIT_AFTER_CLOSE_HOURS}h) đã hết. "
                        "Chỉ Admin mới có thể sửa."
                    ),
                },
            )


def _note_required(
    rec: AttendanceRecord,
    sess: SessionModel,
    note: str | None,
) -> None:
    """
    note BẮT BUỘC khi:
    - Bản ghi đã do người hoặc FaceID đặt (source != system)
    - Sửa buổi đã closed
    KHÔNG bắt buộc khi chuyển từ mặc định hệ thống trong buổi open.
    """
    required = False
    if rec.source != AttendanceSource.system:
        required = True
    if sess.status == SessionStatus.closed:
        required = True

    if required and not note:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "code": "NOTE_REQUIRED",
                "message": "Phải cung cấp ghi chú khi sửa bản ghi điểm danh này.",
            },
        )


# ─────────────────────────── ensure_records (idempotent) ─────────────────────

def ensure_records(db: Session, sess: SessionModel) -> int:
    """
    Tạo bản ghi điểm danh cho mọi sinh viên enrolled chưa có bản ghi.
    - Mặc định: absent / system
    - Có đơn xin vắng approved cho buổi này: excused / leave
    Idempotent: gọi nhiều lần không tạo trùng.
    Trả số bản ghi mới tạo.
    """
    # Lấy danh sách sinh viên enrolled
    enrolled = db.execute(
        select(ClassStudent).where(
            ClassStudent.class_id == sess.class_id,
            ClassStudent.status == ClassStudentStatus.enrolled,
        )
    ).scalars().all()

    if not enrolled:
        return 0

    enrolled_ids = {cs.student_id for cs in enrolled}

    # Các bản ghi đã tồn tại
    existing = db.execute(
        select(AttendanceRecord).where(AttendanceRecord.session_id == sess.id)
    ).scalars().all()
    existing_ids = {r.student_id for r in existing}

    # Đơn xin vắng đã approved cho buổi này
    approved_leaves = db.execute(
        select(LeaveRequest).where(
            LeaveRequest.session_id == sess.id,
            LeaveRequest.status == LeaveRequestStatus.approved,
        )
    ).scalars().all()
    approved_student_ids = {lr.student_id for lr in approved_leaves}

    new_count = 0
    for student_id in enrolled_ids:
        if student_id in existing_ids:
            continue
        if student_id in approved_student_ids:
            rec_status = AttendanceStatus.excused
            rec_source = AttendanceSource.leave
        else:
            rec_status = AttendanceStatus.absent
            rec_source = AttendanceSource.system
        rec = AttendanceRecord(
            session_id=sess.id,
            student_id=student_id,
            status=rec_status,
            source=rec_source,
        )
        db.add(rec)
        new_count += 1

    if new_count > 0:
        db.flush()

    return new_count


# ─────────────────────────── apply_presence ──────────────────────────────────

PresenceResultCode = Literal[
    "present", "late", "OUTSIDE_WINDOW", "already_excused", "no_downgrade"
]

FaceMatchResultCode = Literal[
    "pending_hits",
    "below_threshold",
    "present",
    "late",
    "OUTSIDE_WINDOW",
    "already_excused",
    "no_downgrade",
]


def apply_presence(
    db: Session,
    sess: SessionModel,
    student_id: int,
    source: AttendanceSource,
    confidence: float | None = None,
    actor_id: int | None = None,
    increment_hit: bool = True,
) -> tuple[AttendanceRecord, PresenceResultCode]:
    """
    Xác nhận có mặt theo giờ. Dùng chung cho thủ công (M3) và FaceID (M4).

    Mốc giờ:
    - now <= start + late_after_min  → present
    - now <= start + absent_after_min → late
    - sau đó → OUTSIDE_WINDOW (không đổi)

    Không hạ cấp present/late; excused giữ nguyên.
    Ghi first_seen_at, tăng hit_count, lưu confidence.
    """
    from app.models.class_ import Class

    rec = db.execute(
        select(AttendanceRecord).where(
            AttendanceRecord.session_id == sess.id,
            AttendanceRecord.student_id == student_id,
        )
    ).scalar_one_or_none()

    if not rec:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "RECORD_NOT_FOUND", "message": "Sinh viên không thuộc buổi học này."},
        )

    # excused giữ nguyên
    if rec.status == AttendanceStatus.excused:
        return rec, "already_excused"

    # Không hạ cấp present/late
    if rec.status in (AttendanceStatus.present, AttendanceStatus.late):
        # Vẫn cập nhật hit_count và confidence
        if increment_hit:
            rec.hit_count = (rec.hit_count or 0) + 1
        if confidence is not None:
            rec.confidence = confidence
        db.flush()
        return rec, "no_downgrade"

    # Tính trạng thái theo giờ
    cls = db.get(Class, sess.class_id)
    now = now_local()
    sess_start = datetime.combine(sess.date, sess.start_time).replace(tzinfo=VN_TZ)

    late_deadline = sess_start + timedelta(minutes=cls.late_after_min)
    absent_deadline = sess_start + timedelta(minutes=cls.absent_after_min)

    if now <= late_deadline:
        new_status = AttendanceStatus.present
        result_code: PresenceResultCode = "present"
    elif now <= absent_deadline:
        new_status = AttendanceStatus.late
        result_code = "late"
    else:
        return rec, "OUTSIDE_WINDOW"

    old_status = rec.status
    old_source = rec.source
    now_ts = now_local()

    rec.status = new_status
    rec.source = source
    if rec.first_seen_at is None:
        rec.first_seen_at = now_ts
    if increment_hit:
        rec.hit_count = (rec.hit_count or 0) + 1
    if confidence is not None:
        rec.confidence = confidence
    rec.modified_by = actor_id
    rec.modified_at = now_ts

    # Ghi lịch sử
    hist = AttendanceHistory(
        record_id=rec.id,
        old_status=old_status,
        new_status=new_status,
        old_source=old_source,
        new_source=source,
        note=None,
        changed_by=actor_id,
        changed_at=now_ts,
    )
    db.add(hist)
    db.flush()

    return rec, result_code


def apply_face_match(
    db: Session,
    sess: SessionModel,
    student_id: int,
    score: float | None,
    margin: float | None,
) -> tuple[AttendanceRecord, FaceMatchResultCode]:
    """Áp một lượt match hợp lệ theo ngưỡng và số hit tối thiểu của M4.

    Hàm không commit để toàn bộ log nhận diện và thay đổi điểm danh nằm trong
    cùng một transaction do ``face_service`` quản lý.
    """
    rec = _get_record_or_404(db, sess.id, student_id)
    if (
        score is None
        or margin is None
        or not isfinite(score)
        or not isfinite(margin)
        or score < settings.FACE_MATCH_THRESHOLD
        or margin < settings.FACE_MARGIN_THRESHOLD
    ):
        rec.hit_count = 0
        db.flush()
        return rec, "below_threshold"

    rec.hit_count = (rec.hit_count or 0) + 1
    rec.confidence = score
    if rec.hit_count < settings.FACE_MIN_HITS:
        db.flush()
        return rec, "pending_hits"

    return apply_presence(
        db,
        sess,
        student_id,
        AttendanceSource.face,
        confidence=score,
        increment_hit=False,
    )


def reset_face_hits(db: Session, sess: SessionModel, student_id: int) -> AttendanceRecord:
    """Ngắt chuỗi nhận diện khi khung hình kế tiếp không còn đạt ngưỡng."""
    rec = _get_record_or_404(db, sess.id, student_id)
    rec.hit_count = 0
    db.flush()
    return rec


def reset_missing_face_hits(db: Session, sess: SessionModel, matched_ids: set[int]) -> None:
    """A frame breaks every streak except students validly matched in that frame."""
    query = db.query(AttendanceRecord).filter(
        AttendanceRecord.session_id == sess.id,
        AttendanceRecord.hit_count != 0,
    )
    if matched_ids:
        query = query.filter(AttendanceRecord.student_id.notin_(matched_ids))
    query.update({AttendanceRecord.hit_count: 0}, synchronize_session="fetch")


# ─────────────────────────── patch_attendance ────────────────────────────────

def patch_attendance(
    db: Session,
    session_id: int,
    student_id: int,
    data: AttendancePatch,
    actor: User,
    ip: str | None = None,
) -> AttendanceRecord:
    """Sửa thủ công một bản ghi điểm danh."""
    sess = _get_session_or_404(db, session_id)
    _require_class_lecturer_or_admin(db, actor, sess.class_id)
    _check_edit_permission(db, sess, actor)
    rec = _get_record_or_404(db, session_id, student_id)

    # Optimistic locking
    if data.expected_status is not None and rec.status != data.expected_status:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "STALE_STATE",
                "message": (
                    f"Trạng thái điểm danh đã thay đổi. "
                    f"Mong đợi '{data.expected_status.value}', "
                    f"thực tế '{rec.status.value}'."
                ),
            },
        )

    _note_required(rec, sess, data.note)

    old_status = rec.status
    old_source = rec.source
    now_ts = now_local()

    rec.status = data.status
    rec.source = AttendanceSource.manual
    rec.note = data.note
    rec.modified_by = actor.id
    rec.modified_at = now_ts

    hist = AttendanceHistory(
        record_id=rec.id,
        old_status=old_status,
        new_status=data.status,
        old_source=old_source,
        new_source=AttendanceSource.manual,
        note=data.note,
        changed_by=actor.id,
        changed_at=now_ts,
    )
    db.add(hist)

    log_action(
        db=db,
        user_id=actor.id,
        action="PATCH_ATTENDANCE",
        entity="attendance_records",
        entity_id=str(rec.id),
        detail={
            "session_id": session_id,
            "student_id": student_id,
            "old_status": old_status.value,
            "new_status": data.status.value,
            "note": data.note,
        },
        ip=ip,
    )
    db.commit()
    db.refresh(rec)
    return rec


def bulk_patch_attendance(
    db: Session,
    session_id: int,
    data: BulkAttendancePatch,
    actor: User,
    ip: str | None = None,
) -> BulkAttendanceResult:
    """Sửa hàng loạt bản ghi điểm danh trong một giao dịch."""
    sess = _get_session_or_404(db, session_id)
    _require_class_lecturer_or_admin(db, actor, sess.class_id)
    _check_edit_permission(db, sess, actor)
    if sess.status == SessionStatus.closed and not data.note:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "code": "NOTE_REQUIRED",
                "message": "Phải cung cấp ghi chú khi sửa điểm danh của buổi đã đóng.",
            },
        )

    updated = 0
    skipped = 0
    now_ts = now_local()

    for student_id in data.student_ids:
        rec = db.execute(
            select(AttendanceRecord).where(
                AttendanceRecord.session_id == session_id,
                AttendanceRecord.student_id == student_id,
            )
        ).scalar_one_or_none()
        if not rec:
            skipped += 1
            continue

        try:
            _note_required(rec, sess, data.note)
        except HTTPException:
            skipped += 1
            continue

        old_status = rec.status
        old_source = rec.source
        rec.status = data.status
        rec.source = AttendanceSource.manual
        rec.note = data.note
        rec.modified_by = actor.id
        rec.modified_at = now_ts

        hist = AttendanceHistory(
            record_id=rec.id,
            old_status=old_status,
            new_status=data.status,
            old_source=old_source,
            new_source=AttendanceSource.manual,
            note=data.note,
            changed_by=actor.id,
            changed_at=now_ts,
        )
        db.add(hist)
        updated += 1

    log_action(
        db=db,
        user_id=actor.id,
        action="BULK_PATCH_ATTENDANCE",
        entity="sessions",
        entity_id=str(session_id),
        detail={
            "session_id": session_id,
            "count": updated,
            "status": data.status.value,
            "skipped": skipped,
        },
        ip=ip,
    )
    db.commit()
    return BulkAttendanceResult(updated=updated, skipped=skipped)


def mark_remaining_attendance(
    db: Session,
    session_id: int,
    data: MarkRemainingPatch,
    actor: User,
    ip: str | None = None,
) -> BulkAttendanceResult:
    """Áp status cho các bản ghi còn 'pending' (absent + source system)."""
    sess = _get_session_or_404(db, session_id)
    _require_class_lecturer_or_admin(db, actor, sess.class_id)
    _check_edit_permission(db, sess, actor)
    if sess.status == SessionStatus.closed and not data.note:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "code": "NOTE_REQUIRED",
                "message": "Phải cung cấp ghi chú khi sửa điểm danh của buổi đã đóng.",
            },
        )

    pending_recs = db.execute(
        select(AttendanceRecord).where(
            AttendanceRecord.session_id == session_id,
            AttendanceRecord.status == AttendanceStatus.absent,
            AttendanceRecord.source == AttendanceSource.system,
        )
    ).scalars().all()

    updated = 0
    now_ts = now_local()
    for rec in pending_recs:
        old_status = rec.status
        old_source = rec.source
        rec.status = data.status
        rec.source = AttendanceSource.manual
        rec.note = data.note
        rec.modified_by = actor.id
        rec.modified_at = now_ts

        hist = AttendanceHistory(
            record_id=rec.id,
            old_status=old_status,
            new_status=data.status,
            old_source=old_source,
            new_source=AttendanceSource.manual,
            note=data.note,
            changed_by=actor.id,
            changed_at=now_ts,
        )
        db.add(hist)
        updated += 1

    log_action(
        db=db,
        user_id=actor.id,
        action="MARK_REMAINING_ATTENDANCE",
        entity="sessions",
        entity_id=str(session_id),
        detail={"session_id": session_id, "count": updated, "status": data.status.value},
        ip=ip,
    )
    db.commit()
    return BulkAttendanceResult(updated=updated)


def get_attendance_history(
    db: Session,
    session_id: int,
    student_id: int,
) -> list[AttendanceHistory]:
    """Lấy lịch sử thay đổi điểm danh của một sinh viên trong một buổi."""
    rec = db.execute(
        select(AttendanceRecord).where(
            AttendanceRecord.session_id == session_id,
            AttendanceRecord.student_id == student_id,
        )
    ).scalar_one_or_none()
    if not rec:
        return []
    return (
        db.execute(
            select(AttendanceHistory)
            .where(AttendanceHistory.record_id == rec.id)
            .order_by(AttendanceHistory.changed_at.asc())
        )
        .scalars()
        .all()
    )


def check_in_student(
    db: Session,
    session_id: int,
    student_id: int,
    actor: User,
    ip: str | None = None,
) -> CheckInResult:
    """POST /sessions/{id}/attendance/{student_id}/check-in — điểm danh nhanh thủ công."""
    sess = _get_session_or_404(db, session_id)
    _require_class_lecturer_or_admin(db, actor, sess.class_id)

    if sess.status != SessionStatus.open:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "SESSION_NOT_OPEN",
                "message": "Buổi học không ở trạng thái open.",
            },
        )

    # Lazy auto close check
    from app.services.session_lifecycle_service import lazy_auto_close
    sess = lazy_auto_close(db, sess)
    if sess.status != SessionStatus.open:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "SESSION_NOT_OPEN", "message": "Buổi học đã tự động đóng."},
        )

    rec, result_code = apply_presence(
        db=db,
        sess=sess,
        student_id=student_id,
        source=AttendanceSource.manual,
        actor_id=actor.id,
    )

    messages = {
        "present": "Điểm danh thành công — Có mặt.",
        "late": "Điểm danh thành công — Đi muộn.",
        "OUTSIDE_WINDOW": "Đã qua mốc vắng. Vui lòng chọn trạng thái thủ công.",
        "already_excused": "Sinh viên đã có đơn nghỉ phép được duyệt.",
        "no_downgrade": "Sinh viên đã được điểm danh (không hạ cấp).",
    }

    if result_code not in ("already_excused", "no_downgrade", "OUTSIDE_WINDOW"):
        log_action(
            db=db,
            user_id=actor.id,
            action="CHECK_IN_STUDENT",
            entity="attendance_records",
            entity_id=str(rec.id),
            detail={
                "session_id": session_id,
                "student_id": student_id,
                "result": result_code,
                "new_status": rec.status.value,
            },
            ip=ip,
        )
    # apply_presence vẫn có thể tăng hit_count khi trạng thái không đổi.
    # Commit luôn để không mất thay đổi khi service được gọi ngoài request FastAPI.
    db.commit()
    db.refresh(rec)

    return CheckInResult(
        student_id=student_id,
        result_code=result_code,
        new_status=rec.status,
        message=messages.get(result_code, result_code),
    )
