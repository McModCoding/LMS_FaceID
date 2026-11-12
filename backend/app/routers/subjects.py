from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from app.core.deps import get_db, require_admin
from app.models.user import User
from app.schemas.subject import SubjectCreate, SubjectRead, SubjectUpdate
from app.services.subject_service import (
    create_subject,
    delete_subject,
    get_subject_by_id,
    get_subjects,
    update_subject,
)
from app.utils.ip import get_client_ip

router = APIRouter(prefix="/subjects", tags=["subjects"])


@router.get("", response_model=list[SubjectRead])
def list_subjects(
    department_id: int | None = Query(None),
    q: str | None = Query(None),
    db: Session = Depends(get_db),
    admin_user: User = Depends(require_admin),
):
    return get_subjects(db, department_id=department_id, q=q)


@router.post("", response_model=SubjectRead)
def create_subject_endpoint(
    data: SubjectCreate,
    request: Request,
    db: Session = Depends(get_db),
    admin_user: User = Depends(require_admin),
):
    client_ip = get_client_ip(request)
    return create_subject(
        db=db,
        data=data,
        admin_id=admin_user.id,
        ip=client_ip,
    )


@router.get("/{subject_id}", response_model=SubjectRead)
def get_subject_endpoint(
    subject_id: int,
    db: Session = Depends(get_db),
    admin_user: User = Depends(require_admin),
):
    return get_subject_by_id(db, subject_id)


@router.put("/{subject_id}", response_model=SubjectRead)
def update_subject_endpoint(
    subject_id: int,
    data: SubjectUpdate,
    request: Request,
    db: Session = Depends(get_db),
    admin_user: User = Depends(require_admin),
):
    client_ip = get_client_ip(request)
    return update_subject(
        db=db,
        subject_id=subject_id,
        data=data,
        admin_id=admin_user.id,
        ip=client_ip,
    )


@router.delete("/{subject_id}")
def delete_subject_endpoint(
    subject_id: int,
    request: Request,
    db: Session = Depends(get_db),
    admin_user: User = Depends(require_admin),
):
    client_ip = get_client_ip(request)
    delete_subject(
        db=db,
        subject_id=subject_id,
        admin_id=admin_user.id,
        ip=client_ip,
    )
    return {"message": "Xóa môn học thành công."}
