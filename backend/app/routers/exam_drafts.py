from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db
from app.models.user import User
from app.schemas.exam import ExamDraftIn, ExamList, ExamOut
from app.services import exam_draft_service

router = APIRouter(tags=["Exam drafts"])


@router.get("/classes/{class_id}/exams", response_model=ExamList)
def list_exams(class_id: int, page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100),
               db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return exam_draft_service.list_drafts(db, user, class_id, page, page_size)


@router.post("/classes/{class_id}/exams", response_model=ExamOut, status_code=201)
def create_exam(class_id: int, data: ExamDraftIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return exam_draft_service.exam_out(exam_draft_service.create_draft(db, user, class_id, data))


@router.put("/exams/{exam_id}", response_model=ExamOut)
def update_exam(exam_id: int, data: ExamDraftIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return exam_draft_service.exam_out(exam_draft_service.update_draft(db, user, exam_id, data))


@router.delete("/exams/{exam_id}", status_code=204)
def delete_exam(exam_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    exam_draft_service.delete_draft(db, user, exam_id)
    return Response(status_code=204)
