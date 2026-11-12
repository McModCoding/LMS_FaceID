"""
class_service.py
CRUD lớp học: tạo, xem, sửa, kích hoạt, đóng, xóa.
"""

from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.models.class_ import Class, ClassStatus, ClassStudent, ClassStudentStatus
from app.models.lecturer import Lecturer
from app.models.schedule import Schedule
from app.models.semester import Semester
from app.models.session import Session as SessionModel
from app.models.session import SessionStatus
from app.models.student import Student
from app.models.subject import Subject
from app.models.user import User, UserRole
from app.schemas.class_ import ClassCreate, ClassOut, ClassUpdate
from app.services.audit_service import log_action
from app.services.conflict_service import check_conflicts_for_sessions


def _build_class_out(cls: Class, db: Session) -> ClassOut:
    subject = db.query(Subject).filter(Subject.id == cls.subject_id).first()
    semester = db.query(Semester).filter(Semester.id == cls.semester_id).first()
    lecturer = db.query(Lecturer).filter(Lecturer.id == cls.lecturer_id).first() if cls.lecturer_id else None
    enrolled_count = (
        db.query(func.count(ClassStudent.id))
        .filter(ClassStudent.class_id == cls.id, ClassStudent.status == ClassStudentStatus.enrolled)
        .scalar()
        or 0
    )
    return ClassOut(
        id=cls.id,
        code=cls.code,
        subject_id=cls.subject_id,
        subject_name=subject.name if subject else None,
        subject_code=subject.code if subject else None,
        semester_id=cls.semester_id,
        semester_name=semester.name if semester else None,
        lecturer_id=cls.lecturer_id,
        lecturer_name=lecturer.full_name if lecturer else None,
        lecturer_code=lecturer.code if lecturer else None,
        max_students=cls.max_students,
        enrolled_count=enrolled_count,
        status=cls.status,
        late_after_min=cls.late_after_min,
        absent_after_min=cls.absent_after_min,
        weight_present=cls.weight_present,
        weight_late=cls.weight_late,
        weight_excused=cls.weight_excused,
        attendance_warning_absences=cls.attendance_warning_absences,
        created_at=cls.created_at,
    )


def get_classes_paginated(
    db: Session,
    actor: User,
    page: int = 1,
    page_size: int = 20,
    semester_id: int | None = None,
    subject_id: int | None = None,
    lecturer_id: int | None = None,
    department_id: int | None = None,
    status_filter: ClassStatus | None = None,
    q: str | None = None,
) -> tuple[list[ClassOut], int]:
    query = (
        db.query(Class)
        .filter(Class.is_deleted == False)
        .join(Subject, Class.subject_id == Subject.id)
    )

    # Scope both COUNT and page rows to the authenticated user's membership.
    # EXISTS avoids multiplying rows when other students share the same class.
    if actor.role == UserRole.student:
        membership = (
            db.query(ClassStudent.id)
            .join(Student, Student.id == ClassStudent.student_id)
            .filter(
                ClassStudent.class_id == Class.id,
                ClassStudent.status == ClassStudentStatus.enrolled,
                Student.user_id == actor.id,
                Student.is_deleted == False,
            )
            .exists()
        )
        query = query.filter(membership)
    elif actor.role == UserRole.lecturer:
        assignment = (
            db.query(Lecturer.id)
            .filter(
                Lecturer.id == Class.lecturer_id,
                Lecturer.user_id == actor.id,
                Lecturer.is_deleted == False,
            )
            .exists()
        )
        query = query.filter(assignment)
    elif actor.role != UserRole.admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "FORBIDDEN", "message": "Bạn không có quyền xem danh sách lớp."},
        )

    if semester_id:
        query = query.filter(Class.semester_id == semester_id)
    if subject_id:
        query = query.filter(Class.subject_id == subject_id)
    if lecturer_id:
        query = query.filter(Class.lecturer_id == lecturer_id)
    if department_id:
        query = query.filter(Subject.department_id == department_id)
    if status_filter:
        query = query.filter(Class.status == status_filter)
    if q:
        pattern = f"%{q}%"
        query = query.filter(
            or_(Class.code.ilike(pattern), Subject.name.ilike(pattern))
        )

    total = query.count()
    classes = (
        query.order_by(Class.code.asc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    items = [_build_class_out(c, db) for c in classes]
    return items, total


def get_class_by_id(db: Session, class_id: int) -> Class:
    cls = db.query(Class).filter(Class.id == class_id, Class.is_deleted == False).first()
    if not cls:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "CLASS_NOT_FOUND", "message": "Không tìm thấy lớp học."},
        )
    return cls


def create_class(
    db: Session,
    data: ClassCreate,
    actor_id: int,
    ip: str | None = None,
) -> ClassOut:
    # Kiểm tra code duy nhất
    if db.query(Class).filter(Class.code == data.code, Class.is_deleted == False).first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "CLASS_CODE_EXISTS", "message": f"Mã lớp {data.code} đã tồn tại."},
        )

    # Kiểm tra subject, semester tồn tại
    if not db.query(Subject).filter(Subject.id == data.subject_id).first():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "SUBJECT_NOT_FOUND", "message": "Không tìm thấy môn học."},
        )
    if not db.query(Semester).filter(Semester.id == data.semester_id).first():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "SEMESTER_NOT_FOUND", "message": "Không tìm thấy học kỳ."},
        )
    if data.lecturer_id and not db.query(Lecturer).filter(
        Lecturer.id == data.lecturer_id, Lecturer.is_deleted == False
    ).first():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "LECTURER_NOT_FOUND", "message": "Không tìm thấy giảng viên."},
        )

    cls = Class(
        code=data.code.strip(),
        subject_id=data.subject_id,
        semester_id=data.semester_id,
        lecturer_id=data.lecturer_id,
        max_students=data.max_students,
        status=ClassStatus.draft,
        late_after_min=data.late_after_min,
        absent_after_min=data.absent_after_min,
        weight_present=data.weight_present,
        weight_late=data.weight_late,
        weight_excused=data.weight_excused,
        attendance_warning_absences=data.attendance_warning_absences,
        is_deleted=False,
    )
    db.add(cls)
    db.flush()

    log_action(
        db=db,
        user_id=actor_id,
        action="CREATE_CLASS",
        entity="classes",
        entity_id=str(cls.id),
        detail={"code": cls.code, "subject_id": cls.subject_id, "semester_id": cls.semester_id},
        ip=ip,
    )
    db.commit()
    db.refresh(cls)
    return _build_class_out(cls, db)


def update_class(
    db: Session,
    class_id: int,
    data: ClassUpdate,
    actor_id: int,
    ip: str | None = None,
) -> ClassOut:
    cls = get_class_by_id(db, class_id)
    if cls.status == ClassStatus.closed:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "CLASS_CLOSED", "message": "Lớp đã đóng, không thể sửa."},
        )

    changes: dict = {}

    if data.lecturer_id is not None and data.lecturer_id != cls.lecturer_id:
        if data.lecturer_id and not db.query(Lecturer).filter(
            Lecturer.id == data.lecturer_id, Lecturer.is_deleted == False
        ).first():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "LECTURER_NOT_FOUND", "message": "Không tìm thấy giảng viên."},
            )
        # Kiểm tra xung đột giảng viên mới trên các buổi chưa diễn ra
        upcoming_sessions = (
            db.query(SessionModel)
            .filter(
                SessionModel.class_id == class_id,
                SessionModel.status == SessionStatus.scheduled,
            )
            .all()
        )
        if upcoming_sessions and data.lecturer_id:
            proposed = [(s.date, s.start_time, s.end_time, s.room) for s in upcoming_sessions]
            # Tạm thời dùng class_id khác để check lecturer mới
            conflict_result = check_conflicts_for_sessions(
                db,
                proposed=proposed,
                class_id=class_id,
                lecturer_id=data.lecturer_id,
                exclude_session_ids=[s.id for s in upcoming_sessions],
            )
            if conflict_result.has_conflict:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail={
                        "code": "SCHEDULE_CONFLICT",
                        "message": "Giảng viên mới có xung đột lịch với các buổi chưa diễn ra.",
                        "details": {
                            "conflicts": [
                                {
                                    "conflict_type": c.conflict_type,
                                    "class_id": c.class_id,
                                    "class_code": c.class_code,
                                    "date": str(c.date),
                                    "start_time": str(c.start_time),
                                    "end_time": str(c.end_time),
                                    "message": c.message,
                                }
                                for c in conflict_result.conflicts
                            ]
                        },
                    },
                )
        changes["lecturer_id"] = {"old": cls.lecturer_id, "new": data.lecturer_id}
        cls.lecturer_id = data.lecturer_id

    if data.max_students is not None and data.max_students != cls.max_students:
        enrolled_count = (
            db.query(func.count(ClassStudent.id))
            .filter(
                ClassStudent.class_id == class_id,
                ClassStudent.status == ClassStudentStatus.enrolled,
            )
            .scalar()
            or 0
        )
        if data.max_students < enrolled_count:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "code": "MAX_STUDENTS_BELOW_ENROLLED",
                    "message": f"Sĩ số tối đa không thể nhỏ hơn {enrolled_count} sinh viên đã ghi danh.",
                },
            )
        changes["max_students"] = {"old": cls.max_students, "new": data.max_students}
        cls.max_students = data.max_students
    effective_late_after = data.late_after_min if data.late_after_min is not None else cls.late_after_min
    effective_absent_after = data.absent_after_min if data.absent_after_min is not None else cls.absent_after_min
    if effective_late_after >= effective_absent_after:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "code": "INVALID_ATTENDANCE_THRESHOLD",
                "message": "late_after_min phải nhỏ hơn absent_after_min.",
            },
        )
    if data.late_after_min is not None:
        changes["late_after_min"] = {"old": cls.late_after_min, "new": data.late_after_min}
        cls.late_after_min = data.late_after_min
    if data.absent_after_min is not None:
        changes["absent_after_min"] = {"old": cls.absent_after_min, "new": data.absent_after_min}
        cls.absent_after_min = data.absent_after_min
    if data.weight_present is not None:
        changes["weight_present"] = {"old": cls.weight_present, "new": data.weight_present}
        cls.weight_present = data.weight_present
    if data.weight_late is not None:
        changes["weight_late"] = {"old": cls.weight_late, "new": data.weight_late}
        cls.weight_late = data.weight_late
    if data.weight_excused is not None:
        changes["weight_excused"] = {"old": cls.weight_excused, "new": data.weight_excused}
        cls.weight_excused = data.weight_excused
    if data.attendance_warning_absences is not None:
        changes["attendance_warning_absences"] = {
            "old": cls.attendance_warning_absences,
            "new": data.attendance_warning_absences,
        }
        cls.attendance_warning_absences = data.attendance_warning_absences

    log_action(
        db=db,
        user_id=actor_id,
        action="UPDATE_CLASS",
        entity="classes",
        entity_id=str(cls.id),
        detail={"code": cls.code, "changes": changes},
        ip=ip,
    )
    db.commit()
    db.refresh(cls)
    return _build_class_out(cls, db)


def activate_class(
    db: Session,
    class_id: int,
    actor_id: int,
    ip: str | None = None,
) -> ClassOut:
    cls = get_class_by_id(db, class_id)
    if cls.status != ClassStatus.draft:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "CLASS_NOT_DRAFT", "message": "Chỉ lớp ở trạng thái draft mới được kích hoạt."},
        )

    # Yêu cầu: có giảng viên và ít nhất 1 lịch học
    if not cls.lecturer_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": "MISSING_LECTURER", "message": "Lớp phải có giảng viên trước khi kích hoạt."},
        )
    schedule_count = db.query(Schedule).filter(Schedule.class_id == class_id).count()
    if schedule_count == 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": "MISSING_SCHEDULE", "message": "Lớp phải có ít nhất một lịch học trước khi kích hoạt."},
        )

    cls.status = ClassStatus.active
    log_action(
        db=db,
        user_id=actor_id,
        action="ACTIVATE_CLASS",
        entity="classes",
        entity_id=str(cls.id),
        detail={"code": cls.code, "old_status": "draft", "new_status": "active"},
        ip=ip,
    )
    db.commit()
    db.refresh(cls)
    return _build_class_out(cls, db)


def close_class(
    db: Session,
    class_id: int,
    actor_id: int,
    ip: str | None = None,
) -> ClassOut:
    cls = get_class_by_id(db, class_id)
    if cls.status == ClassStatus.closed:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "CLASS_ALREADY_CLOSED", "message": "Lớp đã đóng."},
        )

    old_status = cls.status.value
    cls.status = ClassStatus.closed
    log_action(
        db=db,
        user_id=actor_id,
        action="CLOSE_CLASS",
        entity="classes",
        entity_id=str(cls.id),
        detail={"code": cls.code, "old_status": old_status, "new_status": "closed"},
        ip=ip,
    )
    db.commit()
    db.refresh(cls)
    return _build_class_out(cls, db)


def delete_class(
    db: Session,
    class_id: int,
    actor_id: int,
    ip: str | None = None,
) -> None:
    cls = get_class_by_id(db, class_id)
    if cls.status != ClassStatus.draft:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "CLASS_NOT_DRAFT", "message": "Chỉ lớp draft mới có thể xóa. Lớp khác hãy đóng lại."},
        )

    # Kiểm tra không có sinh viên enrolled
    enrolled_count = (
        db.query(func.count(ClassStudent.id))
        .filter(ClassStudent.class_id == class_id, ClassStudent.status == ClassStudentStatus.enrolled)
        .scalar()
        or 0
    )
    if enrolled_count > 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "CLASS_HAS_STUDENTS", "message": "Không thể xóa lớp đã có sinh viên ghi danh."},
        )

    # Kiểm tra không có buổi học (kể cả scheduled)
    session_count = db.query(SessionModel).filter(SessionModel.class_id == class_id).count()
    if session_count > 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "CLASS_HAS_SESSIONS", "message": "Không thể xóa lớp đã có buổi học. Hãy xóa lịch trước."},
        )

    cls.is_deleted = True
    log_action(
        db=db,
        user_id=actor_id,
        action="DELETE_CLASS",
        entity="classes",
        entity_id=str(cls.id),
        detail={"code": cls.code},
        ip=ip,
    )
    db.commit()
