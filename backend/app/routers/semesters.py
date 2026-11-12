from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.core.deps import get_db, require_admin
from app.models.user import User
from app.schemas.semester import SemesterCreate, SemesterRead, SemesterUpdate
from app.services.semester_service import (
    create_semester,
    delete_semester,
    get_semester_by_id,
    get_semesters,
    update_semester,
)
from app.utils.ip import get_client_ip

router = APIRouter(prefix="/semesters", tags=["semesters"])


@router.get("", response_model=list[SemesterRead])
def list_semesters(
    db: Session = Depends(get_db),
    admin_user: User = Depends(require_admin),
):
    return get_semesters(db)


@router.post("", response_model=SemesterRead)
def create_semester_endpoint(
    data: SemesterCreate,
    request: Request,
    db: Session = Depends(get_db),
    admin_user: User = Depends(require_admin),
):
    client_ip = get_client_ip(request)
    return create_semester(
        db=db,
        data=data,
        admin_id=admin_user.id,
        ip=client_ip,
    )


@router.get("/{semester_id}", response_model=SemesterRead)
def get_semester_endpoint(
    semester_id: int,
    db: Session = Depends(get_db),
    admin_user: User = Depends(require_admin),
):
    return get_semester_by_id(db, semester_id)


@router.put("/{semester_id}", response_model=SemesterRead)
def update_semester_endpoint(
    semester_id: int,
    data: SemesterUpdate,
    request: Request,
    db: Session = Depends(get_db),
    admin_user: User = Depends(require_admin),
):
    client_ip = get_client_ip(request)
    return update_semester(
        db=db,
        semester_id=semester_id,
        data=data,
        admin_id=admin_user.id,
        ip=client_ip,
    )


@router.delete("/{semester_id}")
def delete_semester_endpoint(
    semester_id: int,
    request: Request,
    db: Session = Depends(get_db),
    admin_user: User = Depends(require_admin),
):
    client_ip = get_client_ip(request)
    delete_semester(
        db=db,
        semester_id=semester_id,
        admin_id=admin_user.id,
        ip=client_ip,
    )
    return {"message": "Xóa học kỳ thành công."}
