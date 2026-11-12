"""
timetable_service.py
Thời khóa biểu: /me/timetable và /admin/timetable.
"""

from __future__ import annotations

from datetime import date

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.class_ import Class, ClassStudent, ClassStudentStatus
from app.models.lecturer import Lecturer
from app.models.session import Session as SessionModel
from app.models.session import SessionStatus
from app.models.subject import Subject
from app.models.user import User, UserRole
from app.schemas.timetable import TimetableResponse, TimetableSessionOut


def _build_session_out(sess: SessionModel, db: Session) -> TimetableSessionOut:
    cls = db.query(Class).filter(Class.id == sess.class_id).first()
    subject = db.query(Subject).filter(Subject.id == cls.subject_id).first() if cls else None
    lecturer = db.query(Lecturer).filter(Lecturer.id == cls.lecturer_id).first() if cls and cls.lecturer_id else None
    return TimetableSessionOut(
        session_id=sess.id,
        class_id=sess.class_id,
        class_code=cls.code if cls else "",
        subject_name=subject.name if subject else "",
        subject_code=subject.code if subject else "",
        date=sess.date,
        start_time=sess.start_time,
        end_time=sess.end_time,
        room=sess.room,
        status=sess.status.value,
        lecturer_id=cls.lecturer_id if cls else None,
        lecturer_name=lecturer.full_name if lecturer else None,
    )


def get_my_timetable(
    db: Session,
    current_user: User,
    from_date: date,
    to_date: date,
) -> TimetableResponse:
    if from_date > to_date:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": "INVALID_DATE_RANGE", "message": "from phải nhỏ hơn hoặc bằng to."},
        )

    if current_user.role == UserRole.lecturer:
        # Giảng viên thấy lớp mình dạy
        lecturer = db.query(Lecturer).filter(Lecturer.user_id == current_user.id, Lecturer.is_deleted == False).first()
        if not lecturer:
            return TimetableResponse(items=[], total=0)

        class_ids = [
            r[0] for r in db.query(Class.id)
            .filter(Class.lecturer_id == lecturer.id, Class.is_deleted == False)
            .all()
        ]
    elif current_user.role == UserRole.student:
        # Sinh viên thấy lớp mình đang enrolled
        from app.models.student import Student
        student = db.query(Student).filter(Student.user_id == current_user.id, Student.is_deleted == False).first()
        if not student:
            return TimetableResponse(items=[], total=0)

        class_ids = [
            r[0] for r in db.query(ClassStudent.class_id)
            .filter(ClassStudent.student_id == student.id, ClassStudent.status == ClassStudentStatus.enrolled)
            .all()
        ]
    else:
        # Admin — dùng admin endpoint thay thế
        class_ids = [r[0] for r in db.query(Class.id).filter(Class.is_deleted == False).all()]

    if not class_ids:
        return TimetableResponse(items=[], total=0)

    sessions = (
        db.query(SessionModel)
        .filter(
            SessionModel.class_id.in_(class_ids),
            SessionModel.date >= from_date,
            SessionModel.date <= to_date,
            SessionModel.status != SessionStatus.cancelled,
        )
        .order_by(SessionModel.date.asc(), SessionModel.start_time.asc())
        .all()
    )

    items = [_build_session_out(s, db) for s in sessions]
    return TimetableResponse(items=items, total=len(items))


def get_admin_timetable(
    db: Session,
    from_date: date,
    to_date: date,
    lecturer_id: int | None = None,
    department_id: int | None = None,
    room: str | None = None,
    class_id: int | None = None,
) -> TimetableResponse:
    if from_date > to_date:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": "INVALID_DATE_RANGE", "message": "from phải nhỏ hơn hoặc bằng to."},
        )

    query = (
        db.query(SessionModel)
        .filter(
            SessionModel.date >= from_date,
            SessionModel.date <= to_date,
            SessionModel.status != SessionStatus.cancelled,
        )
    )

    if class_id:
        query = query.filter(SessionModel.class_id == class_id)
    elif lecturer_id or room or department_id:
        # Cần join với Class để lọc theo lecturer
        query = query.join(Class, SessionModel.class_id == Class.id).filter(Class.is_deleted == False)
        if lecturer_id:
            query = query.filter(Class.lecturer_id == lecturer_id)
        if department_id:
            query = query.join(Subject, Class.subject_id == Subject.id).filter(
                Subject.department_id == department_id
            )
        if room:
            from sqlalchemy import func
            query = query.filter(func.upper(func.trim(SessionModel.room)) == room.strip().upper())

    sessions = query.order_by(SessionModel.date.asc(), SessionModel.start_time.asc()).all()
    items = [_build_session_out(s, db) for s in sessions]
    return TimetableResponse(items=items, total=len(items))
