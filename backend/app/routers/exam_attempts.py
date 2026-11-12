"""Student exam list and attempt endpoints. Exam publication remains unavailable."""

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db
from app.models.user import User
from app.schemas.exam_attempt import AnswerIn, AttemptOut, StudentExamListOut
from app.services import exam_attempt_service

router = APIRouter(tags=["student exams"])


@router.get("/classes/{class_id}/student-exams", response_model=StudentExamListOut)
def list_student_exams(class_id: int, page: int = Query(1, ge=1),
                       page_size: int = Query(20, ge=1, le=100),
                       db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return exam_attempt_service.list_student_exams(db, user, class_id, page, page_size)


@router.post("/exams/{exam_id}/attempts", response_model=AttemptOut)
def start_attempt(exam_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    attempt = exam_attempt_service.begin_attempt(db, user, exam_id)
    return exam_attempt_service.read_attempt(db, user, attempt.id)


@router.get("/attempts/{attempt_id}", response_model=AttemptOut)
def get_attempt(attempt_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return exam_attempt_service.read_attempt(db, user, attempt_id)


@router.put("/attempts/{attempt_id}/answers/{question_id}", status_code=204)
def put_answer(attempt_id: int, question_id: int, data: AnswerIn,
               db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    exam_attempt_service.save_answer(db, user, attempt_id, question_id, data.selected_option_ids, data.essay_text)
    return Response(status_code=204)


@router.post("/attempts/{attempt_id}/submit", response_model=AttemptOut)
def submit_attempt(attempt_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    attempt = exam_attempt_service.submit_attempt(db, user, attempt_id)
    return exam_attempt_service.read_attempt(db, user, attempt.id)
