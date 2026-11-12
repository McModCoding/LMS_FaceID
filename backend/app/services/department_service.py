from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.department import Department
from app.models.lecturer import Lecturer
from app.models.student import Student
from app.models.subject import Subject
from app.schemas.department import DepartmentCreate, DepartmentUpdate
from app.services.audit_service import log_action


def list_departments(db: Session, include_inactive: bool = False) -> list[Department]:
    query = db.query(Department)
    if not include_inactive:
        query = query.filter(Department.is_active == True)
    return query.order_by(Department.code.asc()).all()


def get_department(db: Session, department_id: int) -> Department:
    department = db.query(Department).filter(Department.id == department_id).first()
    if not department:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={"code": "DEPARTMENT_NOT_FOUND", "message": "Không tìm thấy khoa."})
    return department


def create_department(db: Session, data: DepartmentCreate, admin_id: int, ip: str | None) -> Department:
    code = data.code.strip().upper()
    name = data.name.strip()
    if db.query(Department).filter((Department.code == code) | (Department.name == name)).first():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail={"code": "DEPARTMENT_EXISTS", "message": "Mã hoặc tên khoa đã tồn tại."})
    department = Department(code=code, name=name)
    db.add(department)
    db.flush()
    log_action(db, admin_id, "CREATE_DEPARTMENT", "departments", str(department.id), {"code": code, "name": name, "summary": f"Tạo khoa {name}"}, ip)
    db.commit()
    db.refresh(department)
    return department


def update_department(db: Session, department_id: int, data: DepartmentUpdate, admin_id: int, ip: str | None) -> Department:
    department = get_department(db, department_id)
    changes = data.model_dump(exclude_unset=True)
    for key, value in changes.items():
        setattr(department, key, value.strip() if key == "name" else value)
    log_action(db, admin_id, "UPDATE_DEPARTMENT", "departments", str(department.id), {"code": department.code, "changes": list(changes), "summary": f"Cập nhật khoa {department.name}"}, ip)
    db.commit()
    db.refresh(department)
    return department


def deactivate_department(db: Session, department_id: int, admin_id: int, ip: str | None) -> None:
    department = get_department(db, department_id)
    has_references = any((
        db.query(Student).filter(Student.department_id == department_id, Student.is_deleted == False).first(),
        db.query(Lecturer).filter(Lecturer.department_id == department_id, Lecturer.is_deleted == False).first(),
        db.query(Subject).filter(Subject.department_id == department_id).first(),
    ))
    if has_references:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail={"code": "DEPARTMENT_IN_USE", "message": "Không thể ngừng sử dụng khoa đang có sinh viên, giảng viên hoặc môn học."})
    department.is_active = False
    log_action(db, admin_id, "DEACTIVATE_DEPARTMENT", "departments", str(department.id), {"code": department.code, "summary": f"Ngừng sử dụng khoa {department.name}"}, ip)
    db.commit()
