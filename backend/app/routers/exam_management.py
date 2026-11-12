from typing import Literal

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db
from app.models.user import User
from app.schemas.exam import ExamOut
from app.schemas.exam_management import (
    AttemptListOut,
    AttemptReviewOut,
    EssayGradeIn,
    ExamCloseTimeIn,
    ExamEventIn,
    ExamEventListOut,
    ExamEventReceipt,
    ExamResultsOut,
    ExamStatsOut,
)
from app.services import exam_event_service, exam_lifecycle_service, exam_review_service
from app.services.exam_draft_service import exam_out

router = APIRouter(tags=["Exam management"])


@router.post("/exams/{exam_id}/publish", response_model=ExamOut)
def publish_exam(exam_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return exam_out(exam_lifecycle_service.publish_exam(db, user, exam_id))


@router.post("/exams/{exam_id}/close", response_model=ExamOut)
def close_exam(exam_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return exam_out(exam_lifecycle_service.close_exam(db, user, exam_id))


@router.patch("/exams/{exam_id}/close-time", response_model=ExamOut)
def close_time(exam_id: int, data: ExamCloseTimeIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return exam_out(exam_lifecycle_service.update_close_time(db, user, exam_id, data.close_at))


@router.post("/attempts/{attempt_id}/events", response_model=ExamEventReceipt)
def event(attempt_id: int, data: ExamEventIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return exam_event_service.record_event(db, user, attempt_id, data)


@router.get("/attempts/{attempt_id}/events", response_model=ExamEventListOut)
def events(attempt_id: int, page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100),
           db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return exam_review_service.event_list(db, user, attempt_id, page, page_size)


@router.get("/exams/{exam_id}/attempts", response_model=AttemptListOut)
def attempts(exam_id: int, page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100),
             state: Literal["in_progress", "pending_grading", "graded"] | None = None,
             student_id: int | None = None, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return exam_review_service.list_attempts(db, user, exam_id, page, page_size, state, student_id)


@router.get("/attempts/{attempt_id}/review", response_model=AttemptReviewOut)
def review(attempt_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return exam_review_service.review_attempt(db, user, attempt_id)


@router.post("/attempts/{attempt_id}/questions/{question_id}/grade", response_model=AttemptReviewOut)
def grade(attempt_id: int, question_id: int, data: EssayGradeIn,
          db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return exam_review_service.grade_essay(db, user, attempt_id, question_id, data)


@router.get("/exams/{exam_id}/results", response_model=ExamResultsOut)
def results(exam_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return exam_review_service.student_results(db, user, exam_id)


@router.get("/attempts/{attempt_id}/result", response_model=AttemptReviewOut)
def result(attempt_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return exam_review_service.student_attempt_result(db, user, attempt_id)


@router.get("/exams/{exam_id}/stats", response_model=ExamStatsOut)
def stats(exam_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return exam_review_service.statistics(db, user, exam_id)


@router.get("/exams/{exam_id}/export")
def export(exam_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return StreamingResponse(exam_review_service.export_results(db, user, exam_id),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename=ket-qua-kiem-tra-{exam_id}.xlsx"})
