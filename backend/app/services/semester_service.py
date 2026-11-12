from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.semester import Semester
from app.schemas.semester import SemesterCreate, SemesterUpdate
from app.services.audit_service import log_action


def reset_other_semesters_current(db: Session, current_id: int | None = None):
    query = db.query(Semester).filter(Semester.is_current == True)
    if current_id:
        query = query.filter(Semester.id != current_id)
    for sem in query.all():
        sem.is_current = False


def get_semesters(db: Session) -> list[Semester]:
    return db.query(Semester).order_by(Semester.start_date.desc()).all()


def get_semester_by_id(db: Session, semester_id: int) -> Semester:
    sem = db.query(Semester).filter(Semester.id == semester_id).first()
    if not sem:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "SEMESTER_NOT_FOUND", "message": "Không tìm thấy học kỳ."},
        )
    return sem


def create_semester(
    db: Session,
    data: SemesterCreate,
    admin_id: int | None = None,
    ip: str | None = None,
) -> Semester:
    if data.is_current:
        reset_other_semesters_current(db)

    sem = Semester(
        name=data.name,
        start_date=data.start_date,
        end_date=data.end_date,
        is_current=data.is_current,
    )
    db.add(sem)
    db.flush()

    log_action(
        db=db,
        user_id=admin_id,
        action="CREATE_SEMESTER",
        entity="semesters",
        entity_id=str(sem.id),
        detail={
            "name": sem.name,
            "is_current": sem.is_current,
            "summary": f"Tạo mới học kỳ {sem.name}",
        },
        ip=ip,
    )
    db.commit()
    db.refresh(sem)
    return sem


def update_semester(
    db: Session,
    semester_id: int,
    data: SemesterUpdate,
    admin_id: int | None = None,
    ip: str | None = None,
) -> Semester:
    sem = get_semester_by_id(db, semester_id)

    if data.is_current is True:
        reset_other_semesters_current(db, current_id=semester_id)

    update_dict = data.model_dump(exclude_unset=True)
    for key, value in update_dict.items():
        setattr(sem, key, value)

    log_action(
        db=db,
        user_id=admin_id,
        action="UPDATE_SEMESTER",
        entity="semesters",
        entity_id=str(sem.id),
        detail={
            "name": sem.name,
            "updated_fields": list(update_dict.keys()),
            "summary": f"Cập nhật học kỳ {sem.name}",
        },
        ip=ip,
    )
    db.commit()
    db.refresh(sem)
    return sem


def delete_semester(
    db: Session,
    semester_id: int,
    admin_id: int | None = None,
    ip: str | None = None,
):
    sem = get_semester_by_id(db, semester_id)
    sem_name = sem.name
    db.delete(sem)

    log_action(
        db=db,
        user_id=admin_id,
        action="DELETE_SEMESTER",
        entity="semesters",
        entity_id=str(semester_id),
        detail={
            "name": sem_name,
            "summary": f"Xóa học kỳ {sem_name}",
        },
        ip=ip,
    )
    db.commit()
