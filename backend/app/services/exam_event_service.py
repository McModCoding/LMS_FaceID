"""Record configured indicators once per client event, never infer cheating."""

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.exam import Exam
from app.models.exam_attempt import AttemptStatus
from app.models.exam_event import ExamEvent
from app.models.user import User
from app.schemas.exam_management import ExamEventIn
from app.services.exam_attempt_service import GRACE, _finalize, _now, _owned_attempt


def record_event(db: Session, user: User, attempt_id: int, data: ExamEventIn) -> dict:
    attempt = _owned_attempt(db, user, attempt_id, writable=True)
    exam = db.get(Exam, attempt.exam_id)
    def receipt(recorded):
        return {"recorded": recorded, "violation_count": attempt.violation_count,
                "status": attempt.status.value, "is_auto_submitted": attempt.is_auto_submitted}
    existing = db.query(ExamEvent).filter_by(attempt_id=attempt_id, event_id=str(data.event_id)).with_for_update().first()
    if existing:
        if existing.type != data.type:
            raise HTTPException(409, detail={"code": "EVENT_ID_REUSED", "message": "Mã sự kiện đã dùng cho một loại khác."})
        return receipt(True)
    if attempt.status != AttemptStatus.in_progress:
        return receipt(False)
    if _now() > attempt.deadline_at + GRACE:
        _finalize(db, attempt, automatic=True)
        db.commit()
        return receipt(False)
    if not exam.record_events or (data.type == "fullscreen_exit" and not exam.require_fullscreen):
        return receipt(False)
    counted = data.type in exam.violation_types
    db.add(ExamEvent(attempt_id=attempt_id, event_id=str(data.event_id), type=data.type,
                     occurred_at=_now(), counted=counted, meta={}))
    if counted:
        attempt.violation_count += 1
    if (counted and exam.auto_submit_on_violation and exam.max_violations > 0
            and attempt.violation_count >= exam.max_violations):
        _finalize(db, attempt, automatic=True)
    db.commit()
    return receipt(True)
