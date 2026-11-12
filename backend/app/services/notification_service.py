"""Class announcements and in-app notifications for M5."""

from fastapi import HTTPException
from sqlalchemy.orm import Session, joinedload

from app.models.class_ import ClassStudent, ClassStudentStatus
from app.models.learning import Announcement, Notification
from app.models.student import Student
from app.models.user import User, UserRole
from app.services.learning_access import (
    ensure_class_manager,
    ensure_class_writable,
    get_enrolled_student,
)
from app.utils.clock import now_local


def add_notification(
    db: Session,
    user_id: int,
    type_: str,
    title: str,
    body: str,
    link: str | None,
) -> None:
    db.add(Notification(user_id=user_id, type=type_, title=title, body=body, link=link))


def notify_enrolled_students(
    db: Session,
    class_id: int,
    type_: str,
    title: str,
    body: str,
    link: str,
) -> None:
    rows = (
        db.query(Student.user_id)
        .join(ClassStudent, ClassStudent.student_id == Student.id)
        .filter(
            ClassStudent.class_id == class_id,
            ClassStudent.status == ClassStudentStatus.enrolled,
        )
        .all()
    )
    for (user_id,) in rows:
        add_notification(db, user_id, type_, title, body, link)


def list_announcements(db: Session, user: User, class_id: int) -> list[Announcement]:
    if user.role == UserRole.student:
        get_enrolled_student(db, user, class_id)
    else:
        ensure_class_manager(db, user, class_id)
    return (
        db.query(Announcement)
        .filter(Announcement.class_id == class_id)
        .order_by(Announcement.is_pinned.desc(), Announcement.created_at.desc())
        .all()
    )


def create_announcement(db: Session, user: User, class_id: int, data) -> Announcement:
    ensure_class_manager(db, user, class_id)
    ensure_class_writable(db, class_id)
    row = Announcement(class_id=class_id, author_id=user.id, **data.model_dump())
    db.add(row)
    db.flush()
    notify_enrolled_students(
        db,
        class_id,
        "class_announcement",
        "Thông báo lớp",
        data.title,
        f"/student/classes/{class_id}",
    )
    db.commit()
    db.refresh(row)
    return row


def list_system_announcements(db: Session) -> list[Announcement]:
    return (
        db.query(Announcement)
        .options(joinedload(Announcement.author))
        .filter(Announcement.class_id.is_(None))
        .order_by(Announcement.is_pinned.desc(), Announcement.created_at.desc())
        .all()
    )


def create_system_announcement(db: Session, user: User, data) -> Announcement:
    if user.role != UserRole.admin:
        raise HTTPException(
            403,
            detail={"code": "FORBIDDEN", "message": "Chỉ Admin được đăng thông báo hệ thống."},
        )
    row = Announcement(class_id=None, author_id=user.id, **data.model_dump())
    db.add(row)
    db.flush()
    recipients = (
        db.query(User.id)
        .filter(User.id != user.id, User.is_active == True, User.is_deleted == False)
        .all()
    )
    for (user_id,) in recipients:
        add_notification(db, user_id, "system_announcement", data.title, data.content[:500], None)
    db.commit()
    db.refresh(row)
    return row


def list_notifications(db: Session, user: User, page: int, page_size: int) -> dict:
    query = db.query(Notification).filter(Notification.user_id == user.id)
    total = query.count()
    unread = query.filter(Notification.is_read == False).count()
    return {
        "items": query.order_by(Notification.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all(),
        "total": total,
        "unread_count": unread,
        "page": page,
        "page_size": page_size,
    }


def read_notification(db: Session, user: User, notification_id: int) -> Notification:
    row = (
        db.query(Notification)
        .filter(Notification.id == notification_id, Notification.user_id == user.id)
        .first()
    )
    if not row:
        raise HTTPException(
            404,
            detail={"code": "NOTIFICATION_NOT_FOUND", "message": "Không tìm thấy thông báo."},
        )
    if not row.is_read:
        row.is_read = True
        row.read_at = now_local()
        db.commit()
        db.refresh(row)
    return row


def read_all_notifications(db: Session, user: User) -> int:
    count = (
        db.query(Notification)
        .filter(Notification.user_id == user.id, Notification.is_read == False)
        .update(
            {Notification.is_read: True, Notification.read_at: now_local()},
            synchronize_session=False,
        )
    )
    db.commit()
    return count
