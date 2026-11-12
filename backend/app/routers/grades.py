from fastapi import APIRouter, Depends, Query, Response
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db
from app.models.user import User
from app.schemas.grade import GradebookOut, GradeComponentIn, GradeComponentOut, ManualGradeIn
from app.services import grade_service

router = APIRouter(prefix="/classes/{class_id}/gradebook", tags=["Gradebook"])


@router.get("", response_model=GradebookOut)
def read(class_id: int, page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100),
         db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return grade_service.gradebook(db, user, class_id, page, page_size)


@router.post("/components", response_model=GradeComponentOut, status_code=201)
def create(class_id: int, data: GradeComponentIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return grade_service.save_component(db, user, class_id, data)


@router.put("/components/{component_id}", response_model=GradeComponentOut)
def update(class_id: int, component_id: int, data: GradeComponentIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return grade_service.save_component(db, user, class_id, data, component_id)


@router.delete("/components/{component_id}", status_code=204)
def delete(class_id: int, component_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    grade_service.delete_component(db, user, class_id, component_id)
    return Response(status_code=204)


@router.put("/components/{component_id}/students/{student_id}", status_code=204)
def manual(class_id: int, component_id: int, student_id: int, data: ManualGradeIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    grade_service.set_manual(db, user, class_id, component_id, student_id, data)
    return Response(status_code=204)


@router.post("/publish", status_code=204)
def publish(class_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    grade_service.publish(db, user, class_id)
    return Response(status_code=204)


@router.get("/export")
def export(class_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return StreamingResponse(grade_service.export(db, user, class_id), media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename=bang-diem-{class_id}.xlsx"})
