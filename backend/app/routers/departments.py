from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.core.deps import get_db, require_admin
from app.models.user import User
from app.schemas.department import DepartmentCreate, DepartmentRead, DepartmentUpdate
from app.services.department_service import (
    create_department,
    deactivate_department,
    get_department,
    list_departments,
    update_department,
)
from app.utils.ip import get_client_ip

router = APIRouter(prefix="/departments", tags=["departments"])


@router.get("", response_model=list[DepartmentRead])
def get_departments(db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    return list_departments(db, include_inactive=True)


@router.post("", response_model=DepartmentRead)
def post_department(data: DepartmentCreate, request: Request, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    return create_department(db, data, admin.id, get_client_ip(request))


@router.get("/{department_id}", response_model=DepartmentRead)
def get_department_endpoint(department_id: int, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    return get_department(db, department_id)


@router.put("/{department_id}", response_model=DepartmentRead)
def put_department(department_id: int, data: DepartmentUpdate, request: Request, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    return update_department(db, department_id, data, admin.id, get_client_ip(request))


@router.delete("/{department_id}")
def delete_department(department_id: int, request: Request, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    deactivate_department(db, department_id, admin.id, get_client_ip(request))
    return {"message": "Đã ngừng sử dụng khoa."}
