from fastapi import APIRouter, Depends, File, Query, Response, UploadFile
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db
from app.models.question import QuestionDifficulty, QuestionType
from app.models.user import User
from app.schemas.question import QuestionImportIn, QuestionIn, QuestionList, QuestionOut
from app.services import question_import_service, question_service

router = APIRouter(tags=["Question bank"])


@router.get("/subjects/{subject_id}/questions", response_model=QuestionList)
def list_questions(subject_id: int, page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100),
                   search: str | None = Query(None, max_length=200), question_type: QuestionType | None = None,
                   difficulty: QuestionDifficulty | None = None, db: Session = Depends(get_db),
                   user: User = Depends(get_current_user)):
    return question_service.list_questions(db, user, subject_id, page, page_size, search, question_type, difficulty)


@router.post("/subjects/{subject_id}/questions", response_model=QuestionOut, status_code=201)
def create_question(subject_id: int, data: QuestionIn, db: Session = Depends(get_db),
                    user: User = Depends(get_current_user)):
    row = question_service.create_questions(db, user, subject_id, [data])[0]
    return question_service.question_out(user, row)


@router.get("/subjects/{subject_id}/questions/import/template")
def download_template(subject_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    question_service.subject_access(db, user, subject_id)
    return Response(question_import_service.template(), media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    headers={"Content-Disposition": 'attachment; filename="mau-cau-hoi.xlsx"'})


@router.post("/subjects/{subject_id}/questions/import/preview")
async def preview_import(subject_id: int, file: UploadFile = File(...), db: Session = Depends(get_db),
                         user: User = Depends(get_current_user)):
    question_service.subject_access(db, user, subject_id)
    content = await file.read(question_import_service.MAX_BYTES + 1)
    return question_import_service.preview(content, file.filename or "")


@router.post("/subjects/{subject_id}/questions/import/confirm", status_code=201)
def confirm_import(subject_id: int, data: QuestionImportIn, db: Session = Depends(get_db),
                   user: User = Depends(get_current_user)):
    rows = question_service.create_questions(db, user, subject_id, data.items)
    return {"created": len(rows)}


@router.get("/questions/{question_id}", response_model=QuestionOut)
def get_question(question_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return question_service.question_out(user, question_service.get_question(db, user, question_id))


@router.put("/questions/{question_id}", response_model=QuestionOut)
def update_question(question_id: int, data: QuestionIn, db: Session = Depends(get_db),
                    user: User = Depends(get_current_user)):
    return question_service.question_out(user, question_service.update_question(db, user, question_id, data))


@router.delete("/questions/{question_id}", status_code=204)
def delete_question(question_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    question_service.delete_question(db, user, question_id)
    return Response(status_code=204)
