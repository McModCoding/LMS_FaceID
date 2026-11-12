from fastapi import HTTPException, status
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.security import generate_temp_password, get_password_hash
from app.models.department import Department
from app.models.lecturer import Lecturer, LecturerType
from app.models.user import User, UserRole
from app.schemas.lecturer import LecturerCreate, LecturerUpdate
from app.services.audit_service import log_action


def get_lecturers_paginated(
    db: Session,
    page: int = 1,
    page_size: int = 20,
    search: str | None = None,
    type_filter: LecturerType | None = None,
    department_id: int | None = None,
) -> tuple[list[dict], int]:
    query = db.query(Lecturer, User).join(User, Lecturer.user_id == User.id).filter(Lecturer.is_deleted == False)

    if search:
        search_pattern = f"%{search}%"
        query = query.filter(
            or_(
                Lecturer.code.ilike(search_pattern),
                Lecturer.full_name.ilike(search_pattern),
                User.email.ilike(search_pattern),
            )
        )

    if type_filter:
        query = query.filter(Lecturer.type == type_filter)
    if department_id == 0:
        query = query.filter(Lecturer.department_id.is_(None))
    elif department_id:
        query = query.filter(Lecturer.department_id == department_id)

    total = query.count()
    results = query.order_by(Lecturer.code.asc()).offset((page - 1) * page_size).limit(page_size).all()

    items = []
    for lec, usr in results:
        items.append({
            "id": lec.id,
            "user_id": lec.user_id,
            "code": lec.code,
            "full_name": lec.full_name,
            "email": usr.email,
            "department_id": lec.department_id,
            "department_name": lec.department_ref.name if lec.department_ref else None,
            "phone": lec.phone,
            "degree": lec.degree,
            "department": lec.department,
            "type": lec.type,
            "is_deleted": lec.is_deleted,
            "user_is_active": usr.is_active,
            "created_at": lec.created_at,
        })

    return items, total


def get_lecturer_by_id(db: Session, lecturer_id: int) -> dict:
    result = (
        db.query(Lecturer, User)
        .join(User, Lecturer.user_id == User.id)
        .filter(Lecturer.id == lecturer_id, Lecturer.is_deleted == False)
        .first()
    )
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "LECTURER_NOT_FOUND", "message": "Không tìm thấy giảng viên."},
        )
    lec, usr = result
    return {
        "id": lec.id,
        "user_id": lec.user_id,
        "code": lec.code,
        "full_name": lec.full_name,
        "email": usr.email,
        "department_id": lec.department_id,
        "department_name": lec.department_ref.name if lec.department_ref else None,
        "phone": lec.phone,
        "degree": lec.degree,
        "department": lec.department,
        "type": lec.type,
        "is_deleted": lec.is_deleted,
        "user_is_active": usr.is_active,
        "created_at": lec.created_at,
    }


def get_my_lecturer(db: Session, user: User) -> dict:
    if user.role != UserRole.lecturer:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "FORBIDDEN", "message": "Chỉ giảng viên mới xem được hồ sơ này."},
        )
    lecturer = db.query(Lecturer).filter(
        Lecturer.user_id == user.id, Lecturer.is_deleted == False
    ).first()
    if not lecturer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "LECTURER_NOT_FOUND", "message": "Không tìm thấy hồ sơ giảng viên."},
        )
    return get_lecturer_by_id(db, lecturer.id)


def create_lecturer(
    db: Session,
    data: LecturerCreate,
    admin_id: int | None = None,
    ip: str | None = None,
) -> tuple[dict, str]:
    username = data.code.lower().strip()

    # Check if username or code exists
    existing_user = db.query(User).filter(User.username == username).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "LECTURER_CODE_EXISTS", "message": f"Mã/tài khoản giảng viên {data.code} đã tồn tại."},
        )

    existing_email = db.query(User).filter(User.email == data.email).first()
    if existing_email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "EMAIL_EXISTS", "message": f"Email {data.email} đã được sử dụng."},
        )

    temp_password = generate_temp_password(10)
    password_hash = get_password_hash(temp_password)

    user = User(
        username=username,
        email=data.email,
        password_hash=password_hash,
        role=UserRole.lecturer,
        is_active=True,
        must_change_password=True,
        is_deleted=False,
    )
    db.add(user)
    db.flush()

    lec = Lecturer(
        user_id=user.id,
        code=data.code.strip(),
        full_name=data.full_name.strip(),
        phone=data.phone,
        degree=data.degree,
        department=data.department,
        department_id=data.department_id,
        type=data.type,
        is_deleted=False,
    )
    db.add(lec)
    db.flush()

    log_action(
        db=db,
        user_id=admin_id,
        action="CREATE_LECTURER",
        entity="lecturers",
        entity_id=str(lec.id),
        detail={
            "code": lec.code,
            "full_name": lec.full_name,
            "summary": f"Thêm mới giảng viên {lec.code} - {lec.full_name}",
        },
        ip=ip,
    )
    db.commit()
    db.refresh(lec)

    lec_data = {
        "id": lec.id,
        "user_id": lec.user_id,
        "code": lec.code,
        "full_name": lec.full_name,
        "email": user.email,
        "department_id": lec.department_id,
        "department_name": lec.department_ref.name if lec.department_ref else None,
        "phone": lec.phone,
        "degree": lec.degree,
        "department": lec.department,
        "type": lec.type,
        "is_deleted": lec.is_deleted,
        "user_is_active": user.is_active,
        "created_at": lec.created_at,
    }
    return lec_data, temp_password


def update_lecturer(
    db: Session,
    lecturer_id: int,
    data: LecturerUpdate,
    admin_id: int | None = None,
    ip: str | None = None,
) -> dict:
    result = (
        db.query(Lecturer, User)
        .join(User, Lecturer.user_id == User.id)
        .filter(Lecturer.id == lecturer_id, Lecturer.is_deleted == False)
        .first()
    )
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "LECTURER_NOT_FOUND", "message": "Không tìm thấy giảng viên."},
        )
    lec, usr = result
    changes: dict = {}

    if data.email is not None and data.email != usr.email:
        existing_email = db.query(User).filter(User.email == data.email, User.id != usr.id).first()
        if existing_email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"code": "EMAIL_EXISTS", "message": f"Email {data.email} đã được sử dụng."},
            )
        changes["email"] = {"old": usr.email, "new": data.email}
        usr.email = data.email

    if data.is_active is not None and data.is_active != usr.is_active:
        changes["is_active"] = {"old": usr.is_active, "new": data.is_active}
        usr.is_active = data.is_active

    if data.full_name is not None and data.full_name != lec.full_name:
        changes["full_name"] = {"old": lec.full_name, "new": data.full_name}
        lec.full_name = data.full_name
    if data.phone is not None and data.phone != lec.phone:
        changes["phone"] = {"old": lec.phone, "new": data.phone}
        lec.phone = data.phone
    if data.degree is not None and data.degree != lec.degree:
        changes["degree"] = {"old": lec.degree, "new": data.degree}
        lec.degree = data.degree
    if data.department is not None and data.department != lec.department:
        changes["department"] = {"old": lec.department, "new": data.department}
        lec.department = data.department
    if data.department_id is not None and data.department_id != lec.department_id:
        if not db.query(Department).filter(Department.id == data.department_id, Department.is_active == True).first():
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail={"code": "DEPARTMENT_NOT_FOUND", "message": "Khoa được chọn không tồn tại hoặc đã ngừng sử dụng."})
        changes["department_id"] = {"old": lec.department_id, "new": data.department_id}
        lec.department_id = data.department_id
    if data.type is not None and data.type != lec.type:
        changes["type"] = {"old": str(lec.type), "new": str(data.type)}
        lec.type = data.type

    log_action(
        db=db,
        user_id=admin_id,
        action="UPDATE_LECTURER",
        entity="lecturers",
        entity_id=str(lec.id),
        detail={
            "code": lec.code,
            "changes": changes,
            "summary": f"Cập nhật hồ sơ giảng viên {lec.code} ({len(changes)} trường thay đổi)",
        },
        ip=ip,
    )
    db.commit()
    db.refresh(lec)
    db.refresh(usr)

    return {
        "id": lec.id,
        "user_id": lec.user_id,
        "code": lec.code,
        "full_name": lec.full_name,
        "email": usr.email,
        "department_id": lec.department_id,
        "department_name": lec.department_ref.name if lec.department_ref else None,
        "phone": lec.phone,
        "degree": lec.degree,
        "department": lec.department,
        "type": lec.type,
        "is_deleted": lec.is_deleted,
        "user_is_active": usr.is_active,
        "created_at": lec.created_at,
    }


def delete_lecturer(
    db: Session,
    lecturer_id: int,
    admin_id: int | None = None,
    ip: str | None = None,
):
    result = (
        db.query(Lecturer, User)
        .join(User, Lecturer.user_id == User.id)
        .filter(Lecturer.id == lecturer_id, Lecturer.is_deleted == False)
        .first()
    )
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "LECTURER_NOT_FOUND", "message": "Không tìm thấy giảng viên."},
        )
    lec, usr = result
    lec.is_deleted = True
    usr.is_deleted = True
    usr.is_active = False

    log_action(
        db=db,
        user_id=admin_id,
        action="DELETE_LECTURER",
        entity="lecturers",
        entity_id=str(lec.id),
        detail={
            "code": lec.code,
            "full_name": lec.full_name,
            "summary": f"Xóa mềm giảng viên {lec.code} - {lec.full_name}",
        },
        ip=ip,
    )
    db.commit()
