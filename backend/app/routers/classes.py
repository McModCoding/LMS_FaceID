"""
routers/classes.py
Quản lý lớp học phần, ghi danh, lịch, buổi học.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile, status
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db, require_admin
from app.models.class_ import Class, ClassStatus, ClassStudentStatus
from app.models.user import User, UserRole
from app.schemas.class_ import (
    ClassCreate,
    ClassListResponse,
    ClassOut,
    ClassStudentListResponse,
    ClassStudentOut,
    ClassUpdate,
    EnrollmentImportConfirmRequest,
    EnrollmentImportPreview,
    EnrollStudentsRequest,
)
from app.schemas.schedule import ScheduleCreate, ScheduleOut, ScheduleUpdate
from app.schemas.session import SessionListResponse, SessionMakeupCreate, SessionOut
from app.services import class_service, enrollment_service, schedule_service, session_service
from app.utils.ip import get_client_ip

router = APIRouter(tags=["Classes"])


def _get_class_access(
    class_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> tuple[User, Class]:
    """
    Phân quyền xem lớp:
    - Admin: xem tất cả
    - Giảng viên: chỉ lớp mình dạy
    - Sinh viên: chỉ lớp mình đang enrolled
    """
    from app.models.class_ import ClassStudent
    from app.models.lecturer import Lecturer
    from app.models.student import Student

    cls = db.query(Class).filter(Class.id == class_id, Class.is_deleted == False).first()
    if not cls:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "CLASS_NOT_FOUND", "message": "Không tìm thấy lớp học."},
        )

    if current_user.role == UserRole.admin:
        return current_user, cls

    if current_user.role == UserRole.lecturer:
        lecturer = db.query(Lecturer).filter(
            Lecturer.user_id == current_user.id, Lecturer.is_deleted == False
        ).first()
        if not lecturer or cls.lecturer_id != lecturer.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"code": "FORBIDDEN", "message": "Bạn không có quyền xem lớp này."},
            )
        return current_user, cls

    if current_user.role == UserRole.student:
        student = db.query(Student).filter(
            Student.user_id == current_user.id, Student.is_deleted == False
        ).first()
        if not student:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail={"code": "FORBIDDEN", "message": ""})
        from app.models.class_ import ClassStudentStatus
        enrolled = db.query(ClassStudent).filter(
            ClassStudent.class_id == class_id,
            ClassStudent.student_id == student.id,
            ClassStudent.status == ClassStudentStatus.enrolled,
        ).first()
        if not enrolled:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"code": "FORBIDDEN", "message": "Bạn không thuộc lớp này."},
            )
        return current_user, cls

    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail={"code": "FORBIDDEN", "message": ""})


# ============================================================= /classes
@router.get("/classes", response_model=ClassListResponse)
def list_classes(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    semester_id: int | None = None,
    subject_id: int | None = None,
    lecturer_id: int | None = None,
    department_id: int | None = None,
    class_status: ClassStatus | None = Query(None, alias="status"),
    q: str | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Liệt kê lớp học.
    - Admin: tất cả lớp.
    - Giảng viên: chỉ lớp mình dạy.
    - Sinh viên: chỉ lớp mình enrolled.
    """
    items, total = class_service.get_classes_paginated(
        db,
        actor=current_user,
        page=page,
        page_size=page_size,
        semester_id=semester_id,
        subject_id=subject_id,
        lecturer_id=lecturer_id,
        department_id=department_id,
        status_filter=class_status,
        q=q,
    )

    return ClassListResponse(items=items, total=total, page=page, page_size=page_size)


@router.post("/classes", response_model=ClassOut, status_code=status.HTTP_201_CREATED)
def create_class(
    data: ClassCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    return class_service.create_class(db, data, current_user.id, get_client_ip(request))


@router.get("/classes/{class_id}", response_model=ClassOut)
def get_class(
    class_id: int,
    db: Session = Depends(get_db),
    access: tuple = Depends(_get_class_access),
):
    user, cls = access
    return class_service._build_class_out(cls, db)


@router.patch("/classes/{class_id}", response_model=ClassOut)
def update_class(
    class_id: int,
    data: ClassUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    return class_service.update_class(db, class_id, data, current_user.id, get_client_ip(request))


@router.delete("/classes/{class_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_class(
    class_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    class_service.delete_class(db, class_id, current_user.id, get_client_ip(request))


@router.post("/classes/{class_id}/activate", response_model=ClassOut)
def activate_class(
    class_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    return class_service.activate_class(db, class_id, current_user.id, get_client_ip(request))


@router.post("/classes/{class_id}/close", response_model=ClassOut)
def close_class(
    class_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    return class_service.close_class(db, class_id, current_user.id, get_client_ip(request))


# ============================================================ /classes/{id}/students
@router.get("/classes/{class_id}/students", response_model=ClassStudentListResponse)
def list_class_students(
    class_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    q: str | None = None,
    student_status: ClassStudentStatus | None = Query(None, alias="status"),
    db: Session = Depends(get_db),
    access: tuple = Depends(_get_class_access),
):
    user, cls = access
    # Sinh viên không được xem danh sách sinh viên khác
    if user.role == UserRole.student:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "FORBIDDEN", "message": "Sinh viên không có quyền xem danh sách lớp."},
        )
    return enrollment_service.get_class_students(
        db, class_id, page=page, page_size=page_size, status_filter=student_status, q=q
    )


@router.post("/classes/{class_id}/students", response_model=list[ClassStudentOut])
def enroll_students(
    class_id: int,
    data: EnrollStudentsRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    return enrollment_service.enroll_students(db, class_id, data.student_ids, current_user.id, get_client_ip(request))


@router.delete("/classes/{class_id}/students/{student_id}", status_code=status.HTTP_204_NO_CONTENT)
def drop_student(
    class_id: int,
    student_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    enrollment_service.drop_student(db, class_id, student_id, current_user.id, get_client_ip(request))


@router.post("/classes/{class_id}/students/import/preview", response_model=EnrollmentImportPreview)
def preview_import_students(
    class_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    file_bytes = file.file.read()
    return enrollment_service.preview_import_enrollment(db, class_id, file_bytes)


@router.post("/classes/{class_id}/students/import/confirm")
def confirm_import_students(
    class_id: int,
    data: EnrollmentImportConfirmRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    return enrollment_service.confirm_import_enrollment(
        db, class_id, data.valid_rows, current_user.id, get_client_ip(request)
    )


# ============================================================ /classes/{id}/schedules
@router.get("/classes/{class_id}/schedules", response_model=list[ScheduleOut])
def list_schedules(
    class_id: int,
    db: Session = Depends(get_db),
    access: tuple = Depends(_get_class_access),
):
    user, cls = access
    return schedule_service.get_schedules(db, class_id)


@router.post("/classes/{class_id}/schedules", response_model=ScheduleOut, status_code=status.HTTP_201_CREATED)
def create_schedule(
    class_id: int,
    data: ScheduleCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Admin hoặc giảng viên của lớp
    _require_admin_or_class_lecturer(db, current_user, class_id)
    return schedule_service.create_schedule(db, class_id, data, current_user.id, get_client_ip(request))


@router.patch("/classes/{class_id}/schedules/{schedule_id}", response_model=ScheduleOut)
def update_schedule(
    class_id: int,
    schedule_id: int,
    data: ScheduleUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_admin_or_class_lecturer(db, current_user, class_id)
    return schedule_service.update_schedule(db, class_id, schedule_id, data, current_user.id, get_client_ip(request))


@router.delete("/classes/{class_id}/schedules/{schedule_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_schedule(
    class_id: int,
    schedule_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_admin_or_class_lecturer(db, current_user, class_id)
    schedule_service.delete_schedule(db, class_id, schedule_id, current_user.id, get_client_ip(request))


# ============================================================ /classes/{id}/sessions
@router.get("/classes/{class_id}/sessions", response_model=SessionListResponse)
def list_sessions(
    class_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    session_status: str | None = Query(None, alias="status"),
    db: Session = Depends(get_db),
    access: tuple = Depends(_get_class_access),
):
    from app.models.session import SessionStatus
    status_filter = None
    if session_status:
        try:
            status_filter = SessionStatus(session_status)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={"code": "INVALID_STATUS", "message": f"Trạng thái không hợp lệ: {session_status}"},
            )
    return session_service.get_sessions(db, class_id, page=page, page_size=page_size, status_filter=status_filter)


@router.post("/classes/{class_id}/sessions", response_model=SessionOut, status_code=status.HTTP_201_CREATED)
def create_makeup_session(
    class_id: int,
    data: SessionMakeupCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Thêm buổi bù thủ công."""
    _require_admin_or_class_lecturer(db, current_user, class_id)
    return session_service.create_makeup_session(db, class_id, data, current_user.id, get_client_ip(request))


# ============================================================ Helper
def _require_admin_or_class_lecturer(db: Session, user: User, class_id: int) -> None:
    """Kiểm tra user là admin hoặc giảng viên của lớp class_id."""
    if user.role == UserRole.admin:
        return
    if user.role == UserRole.lecturer:
        from app.models.lecturer import Lecturer
        lec = db.query(Lecturer).filter(Lecturer.user_id == user.id, Lecturer.is_deleted == False).first()
        cls = db.query(Class).filter(Class.id == class_id, Class.is_deleted == False).first()
        if lec and cls and cls.lecturer_id == lec.id:
            return
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail={"code": "FORBIDDEN", "message": "Bạn không có quyền thực hiện thao tác này."},
    )
