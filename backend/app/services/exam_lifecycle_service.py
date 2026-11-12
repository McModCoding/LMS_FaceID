"""Publishing and post-start configuration, serialized with attempt creation."""

from datetime import timedelta

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.class_ import Class
from app.models.exam import Exam, ExamStatus
from app.models.exam_attempt import AttemptStatus, ExamAttempt
from app.models.user import User
from app.services.audit_service import log_action
from app.services.exam_attempt_service import GRACE, _finalize, _now
from app.services.exam_content_service import freeze_exam_content
from app.services.learning_access import (
    ensure_class_manager,
    ensure_class_writable,
    get_class_or_404,
)
from app.services.notification_service import notify_enrolled_students


def managed_exam(db: Session, user: User, exam_id: int, *, writable: bool = False) -> Exam:
    lookup = db.get(Exam, exam_id)
    if not lookup:
        raise HTTPException(404, detail={"code": "EXAM_NOT_FOUND", "message": "Không tìm thấy bài kiểm tra."})
    # Same lock order as starting/saving an attempt: class, exam, attempt.
    db.query(Class).filter(Class.id == lookup.class_id).with_for_update().first()
    get_class_or_404(db, lookup.class_id)
    ensure_class_manager(db, user, lookup.class_id)
    if writable:
        ensure_class_writable(db, lookup.class_id)
    return db.query(Exam).filter(Exam.id == exam_id).populate_existing().with_for_update().one()


def publish_exam(db: Session, user: User, exam_id: int) -> Exam:
    exam = managed_exam(db, user, exam_id, writable=True)
    if exam.status != ExamStatus.draft:
        raise HTTPException(409, detail={"code": "EXAM_NOT_DRAFT", "message": "Chỉ công bố được đề nháp; đề này đã được xử lý."})
    if exam.close_at <= _now():
        raise HTTPException(409, detail={"code": "EXAM_CLOSED", "message": "Giờ đóng đã qua. Hãy sửa khung giờ trước khi công bố."})
    try:
        exam.status = ExamStatus.published
        db.flush()
        freeze_exam_content(db, exam.id)
        notify_enrolled_students(db, exam.class_id, "exam_published", "Bài kiểm tra mới",
            f"{exam.title} đã được công bố. Kiểm tra khung giờ trước khi làm bài.",
            f"/student/classes/{exam.class_id}?tab=exams")
        log_action(db, user.id, "PUBLISH_EXAM", "exams", str(exam.id), {"class_id": exam.class_id})
        db.commit()
    except Exception:
        db.rollback()
        raise
    return exam


def update_close_time(db: Session, user: User, exam_id: int, close_at) -> Exam:
    exam = managed_exam(db, user, exam_id, writable=True)
    if exam.status != ExamStatus.published:
        raise HTTPException(409, detail={"code": "EXAM_NOT_PUBLISHED", "message": "Chỉ đổi giờ đóng của đề đã công bố và chưa đóng."})
    new_time = close_at.replace(tzinfo=None)
    if new_time <= exam.open_at:
        raise HTTPException(422, detail={"code": "INVALID_EXAM_WINDOW", "message": "Giờ đóng phải sau giờ mở."})
    old_time = exam.close_at
    attempts = db.query(ExamAttempt).filter_by(exam_id=exam_id, status=AttemptStatus.in_progress).order_by(ExamAttempt.id).populate_existing().with_for_update().all()
    for attempt in attempts:
        if _now() > attempt.deadline_at + GRACE:
            _finalize(db, attempt, automatic=True)
        else:
            attempt.deadline_at = min(attempt.started_at + timedelta(minutes=exam.duration_min), new_time)
            if _now() > attempt.deadline_at + GRACE:
                _finalize(db, attempt, automatic=True)
    exam.close_at = new_time
    log_action(db, user.id, "UPDATE_EXAM_CLOSE_TIME", "exams", str(exam.id),
               {"old": old_time.isoformat(), "new": new_time.isoformat()})
    db.commit()
    return exam


def close_exam(db: Session, user: User, exam_id: int) -> Exam:
    exam = managed_exam(db, user, exam_id, writable=True)
    if exam.status != ExamStatus.published:
        raise HTTPException(409, detail={"code": "EXAM_NOT_PUBLISHED", "message": "Đề chưa công bố hoặc đã đóng."})
    attempts = db.query(ExamAttempt).filter_by(exam_id=exam_id, status=AttemptStatus.in_progress).order_by(ExamAttempt.id).populate_existing().with_for_update().all()
    for attempt in attempts:
        _finalize(db, attempt, automatic=True)
    exam.status = ExamStatus.closed
    log_action(db, user.id, "CLOSE_EXAM", "exams", str(exam.id), {"auto_submitted": len(attempts)})
    db.commit()
    return exam
