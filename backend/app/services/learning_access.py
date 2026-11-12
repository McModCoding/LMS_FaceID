"""Shared authorization and class-state guards for M5 learning services."""

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.class_ import Class, ClassStatus, ClassStudent, ClassStudentStatus
from app.models.lecturer import Lecturer
from app.models.student import Student
from app.models.user import User, UserRole


def get_class_or_404(db: Session, class_id: int) -> Class:
    entity = db.get(Class, class_id)
    if not entity or entity.is_deleted:
        raise HTTPException(
            404,
            detail={"code": "CLASS_NOT_FOUND", "message": "Không tìm thấy lớp học phần."},
        )
    return entity


def ensure_class_manager(db: Session, user: User, class_id: int) -> None:
    if user.role == UserRole.admin:
        return
    lecturer = (
        db.query(Lecturer)
        .filter(Lecturer.user_id == user.id, Lecturer.is_deleted == False)
        .first()
    )
    class_ = get_class_or_404(db, class_id)
    if user.role != UserRole.lecturer or not lecturer or class_.lecturer_id != lecturer.id:
        raise HTTPException(
            403,
            detail={"code": "FORBIDDEN", "message": "Bạn không phụ trách lớp học phần này."},
        )


def ensure_class_writable(db: Session, class_id: int) -> Class:
    class_ = get_class_or_404(db, class_id)
    if class_.status == ClassStatus.closed:
        raise HTTPException(
            409,
            detail={
                "code": "CLASS_CLOSED",
                "message": "Lớp học phần đã đóng và chỉ còn ở chế độ xem.",
            },
        )
    return class_


def get_enrolled_student(db: Session, user: User, class_id: int) -> Student:
    student = (
        db.query(Student)
        .filter(Student.user_id == user.id, Student.is_deleted == False)
        .first()
    )
    enrollment = (
        student
        and db.query(ClassStudent)
        .filter(
            ClassStudent.class_id == class_id,
            ClassStudent.student_id == student.id,
            ClassStudent.status == ClassStudentStatus.enrolled,
        )
        .first()
    )
    if not enrollment:
        raise HTTPException(
            403,
            detail={"code": "NOT_ENROLLED", "message": "Bạn không thuộc lớp học phần này."},
        )
    return student
