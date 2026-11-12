from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.department import Department
from app.models.subject import Subject
from app.schemas.subject import SubjectCreate, SubjectUpdate
from app.services.audit_service import log_action


def get_subjects(db: Session, department_id: int | None = None, q: str | None = None) -> list[Subject]:
    query = db.query(Subject)
    if department_id == 0:
        query = query.filter(Subject.department_id.is_(None))
    elif department_id is not None:
        query = query.filter(Subject.department_id == department_id)
    if q and q.strip():
        from sqlalchemy import or_

        term = f"%{q.strip()}%"
        query = query.filter(or_(Subject.code.ilike(term), Subject.name.ilike(term)))
    return query.order_by(Subject.code.asc()).all()


def get_subject_by_id(db: Session, subject_id: int) -> Subject:
    subj = db.query(Subject).filter(Subject.id == subject_id).first()
    if not subj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "SUBJECT_NOT_FOUND", "message": "Không tìm thấy môn học."},
        )
    return subj


def create_subject(
    db: Session,
    data: SubjectCreate,
    admin_id: int | None = None,
    ip: str | None = None,
) -> Subject:
    code_upper = data.code.upper().strip()
    existing = db.query(Subject).filter(Subject.code == code_upper).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "DUPLICATE_CODE", "message": f"Mã môn học {data.code} đã tồn tại."},
        )
    if data.department_id is not None and not db.query(Department).filter(
        Department.id == data.department_id, Department.is_active == True
    ).first():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": "INVALID_DEPARTMENT", "message": "Khoa không tồn tại hoặc đã ngừng sử dụng."},
        )
    subj = Subject(
        code=code_upper,
        name=data.name.strip(),
        credits=data.credits,
        department_id=data.department_id,
    )
    db.add(subj)
    db.flush()

    log_action(
        db=db,
        user_id=admin_id,
        action="CREATE_SUBJECT",
        entity="subjects",
        entity_id=str(subj.id),
        detail={
            "code": subj.code,
            "name": subj.name,
            "credits": subj.credits,
            "summary": f"Tạo mới môn học {subj.code} - {subj.name}",
        },
        ip=ip,
    )
    db.commit()
    db.refresh(subj)
    return subj


def update_subject(
    db: Session,
    subject_id: int,
    data: SubjectUpdate,
    admin_id: int | None = None,
    ip: str | None = None,
) -> Subject:
    subj = get_subject_by_id(db, subject_id)
    if data.code is not None and data.code.upper().strip() != subj.code:
        existing = db.query(Subject).filter(
            Subject.code == data.code.upper().strip(), Subject.id != subject_id
        ).first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"code": "DUPLICATE_CODE", "message": f"Mã môn học {data.code} đã tồn tại."},
            )
    update_dict = data.model_dump(exclude_unset=True)
    if (
        "department_id" in update_dict
        and update_dict["department_id"] is not None
        and not db.query(Department).filter(
            Department.id == update_dict["department_id"], Department.is_active == True
        ).first()
    ):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": "INVALID_DEPARTMENT", "message": "Khoa không tồn tại hoặc đã ngừng sử dụng."},
        )
    if "code" in update_dict:
        update_dict["code"] = update_dict["code"].upper().strip()
    if "name" in update_dict:
        update_dict["name"] = update_dict["name"].strip()
    for key, value in update_dict.items():
        setattr(subj, key, value)

    log_action(
        db=db,
        user_id=admin_id,
        action="UPDATE_SUBJECT",
        entity="subjects",
        entity_id=str(subj.id),
        detail={
            "code": subj.code,
            "name": subj.name,
            "summary": f"Cập nhật môn học {subj.code} - {subj.name}",
        },
        ip=ip,
    )
    db.commit()
    db.refresh(subj)
    return subj


def delete_subject(
    db: Session,
    subject_id: int,
    admin_id: int | None = None,
    ip: str | None = None,
):
    subj = get_subject_by_id(db, subject_id)
    subj_code = subj.code
    subj_name = subj.name
    db.delete(subj)

    log_action(
        db=db,
        user_id=admin_id,
        action="DELETE_SUBJECT",
        entity="subjects",
        entity_id=str(subject_id),
        detail={
            "code": subj_code,
            "name": subj_name,
            "summary": f"Xóa môn học {subj_code} - {subj_name}",
        },
        ip=ip,
    )
    db.commit()
