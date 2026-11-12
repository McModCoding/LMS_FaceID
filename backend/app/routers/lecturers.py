from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db, require_admin
from app.models.lecturer import LecturerType
from app.models.user import User
from app.schemas.lecturer import (
    LecturerCreate,
    LecturerPaginatedResponse,
    LecturerRead,
    LecturerUpdate,
    LecturerWithPasswordResponse,
)
from app.services.lecturer_service import (
    create_lecturer,
    delete_lecturer,
    get_lecturer_by_id,
    get_lecturers_paginated,
    get_my_lecturer,
    update_lecturer,
)
from app.utils.ip import get_client_ip

router = APIRouter(prefix="/lecturers", tags=["lecturers"])


@router.get("", response_model=LecturerPaginatedResponse)
def list_lecturers(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: str | None = Query(None),
    q: str | None = Query(None),
    type: LecturerType | None = Query(None),
    department_id: int | None = Query(None),
    db: Session = Depends(get_db),
    admin_user: User = Depends(require_admin),
):
    query_search = search or q
    items, total = get_lecturers_paginated(
        db, page=page, page_size=page_size, search=query_search, type_filter=type, department_id=department_id
    )
    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.post("", response_model=LecturerWithPasswordResponse)
def create_lecturer_endpoint(
    data: LecturerCreate,
    request: Request,
    db: Session = Depends(get_db),
    admin_user: User = Depends(require_admin),
):
    client_ip = get_client_ip(request)
    lec_data, temp_password = create_lecturer(
        db=db,
        data=data,
        admin_id=admin_user.id,
        ip=client_ip,
    )
    return {
        "lecturer": lec_data,
        "temp_password": temp_password,
    }


@router.get("/me", response_model=LecturerRead)
def get_my_lecturer_endpoint(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return get_my_lecturer(db, current_user)


@router.get("/{lecturer_id}", response_model=LecturerRead)
def get_lecturer_endpoint(
    lecturer_id: int,
    db: Session = Depends(get_db),
    admin_user: User = Depends(require_admin),
):
    return get_lecturer_by_id(db, lecturer_id)


@router.put("/{lecturer_id}", response_model=LecturerRead)
def update_lecturer_endpoint(
    lecturer_id: int,
    data: LecturerUpdate,
    request: Request,
    db: Session = Depends(get_db),
    admin_user: User = Depends(require_admin),
):
    client_ip = get_client_ip(request)
    return update_lecturer(
        db=db,
        lecturer_id=lecturer_id,
        data=data,
        admin_id=admin_user.id,
        ip=client_ip,
    )


@router.delete("/{lecturer_id}")
def delete_lecturer_endpoint(
    lecturer_id: int,
    request: Request,
    db: Session = Depends(get_db),
    admin_user: User = Depends(require_admin),
):
    client_ip = get_client_ip(request)
    delete_lecturer(
        db=db,
        lecturer_id=lecturer_id,
        admin_id=admin_user.id,
        ip=client_ip,
    )
    return {"message": "Xóa giảng viên thành công."}
