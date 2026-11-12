from fastapi import APIRouter, Depends, File, Query, Request, UploadFile
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db, require_admin
from app.models.student import StudentStatus
from app.models.user import User
from app.schemas.student import (
    StudentCreate,
    StudentImportConfirmRequest,
    StudentImportPreviewResponse,
    StudentPaginatedResponse,
    StudentRead,
    StudentUpdate,
    StudentWithPasswordResponse,
)
from app.services.student_service import (
    confirm_import_students,
    create_student,
    delete_student,
    export_students_service,
    get_my_student,
    get_student_by_id,
    get_students_paginated,
    preview_import_students,
    update_student,
)
from app.utils.excel import generate_student_import_template
from app.utils.ip import get_client_ip

router = APIRouter(prefix="/students", tags=["students"])


@router.get("", response_model=StudentPaginatedResponse)
def list_students(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: str | None = Query(None),
    q: str | None = Query(None),
    status: StudentStatus | None = Query(None),
    department_id: int | None = Query(None),
    db: Session = Depends(get_db),
    admin_user: User = Depends(require_admin),
):
    query_search = search or q
    items, total = get_students_paginated(
        db, page=page, page_size=page_size, search=query_search, status_filter=status, department_id=department_id
    )
    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.post("", response_model=StudentWithPasswordResponse)
def create_student_endpoint(
    data: StudentCreate,
    request: Request,
    db: Session = Depends(get_db),
    admin_user: User = Depends(require_admin),
):
    client_ip = get_client_ip(request)
    st_data, temp_password = create_student(
        db=db,
        data=data,
        admin_id=admin_user.id,
        ip=client_ip,
    )
    return {
        "student": st_data,
        "temp_password": temp_password,
    }


@router.get("/import/template")
def get_import_template(admin_user: User = Depends(require_admin)):
    content = generate_student_import_template()
    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=student_import_template.xlsx"},
    )


@router.post("/import/preview", response_model=StudentImportPreviewResponse)
async def preview_import(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    admin_user: User = Depends(require_admin),
):
    file_bytes = await file.read()
    return preview_import_students(db, file_bytes)


@router.post("/import/confirm")
def confirm_import(
    data: StudentImportConfirmRequest,
    request: Request,
    db: Session = Depends(get_db),
    admin_user: User = Depends(require_admin),
):
    client_ip = get_client_ip(request)
    created_students, excel_bytes = confirm_import_students(
        db=db,
        valid_rows=data.valid_rows,
        admin_id=admin_user.id,
        ip=client_ip,
    )
    return Response(
        content=excel_bytes,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=student_import_result.xlsx"},
    )


@router.get("/export")
def export_students(
    db: Session = Depends(get_db),
    admin_user: User = Depends(require_admin),
):
    content = export_students_service(db)
    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=students_export.xlsx"},
    )


@router.get("/me", response_model=StudentRead)
def get_my_student_endpoint(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return get_my_student(db, current_user)


@router.get("/{student_id}", response_model=StudentRead)
def get_student_endpoint(
    student_id: int,
    db: Session = Depends(get_db),
    admin_user: User = Depends(require_admin),
):
    return get_student_by_id(db, student_id)


@router.put("/{student_id}", response_model=StudentRead)
def update_student_endpoint(
    student_id: int,
    data: StudentUpdate,
    request: Request,
    db: Session = Depends(get_db),
    admin_user: User = Depends(require_admin),
):
    client_ip = get_client_ip(request)
    return update_student(
        db=db,
        student_id=student_id,
        data=data,
        admin_id=admin_user.id,
        ip=client_ip,
    )


@router.delete("/{student_id}")
def delete_student_endpoint(
    student_id: int,
    request: Request,
    db: Session = Depends(get_db),
    admin_user: User = Depends(require_admin),
):
    client_ip = get_client_ip(request)
    delete_student(
        db=db,
        student_id=student_id,
        admin_id=admin_user.id,
        ip=client_ip,
    )
    return {"message": "Xóa sinh viên thành công."}
