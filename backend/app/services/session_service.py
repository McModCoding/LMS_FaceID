"""
session_service.py
Quản lý buổi học: liệt kê, sửa một buổi, hủy, thêm buổi bù.
"""

from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.class_ import Class, ClassStatus
from app.models.session import Session as SessionModel
from app.models.session import SessionStatus
from app.schemas.session import SessionListResponse, SessionMakeupCreate, SessionOut, SessionUpdate
from app.services.audit_service import log_action
from app.services.conflict_service import check_conflicts_for_sessions


def _get_class_or_404(db: Session, class_id: int) -> Class:
    cls = db.query(Class).filter(Class.id == class_id, Class.is_deleted == False).first()
    if not cls:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "CLASS_NOT_FOUND", "message": "Không tìm thấy lớp học."},
        )
    return cls


def _get_session_or_404(db: Session, session_id: int) -> SessionModel:
    sess = db.query(SessionModel).filter(SessionModel.id == session_id).first()
    if not sess:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "SESSION_NOT_FOUND", "message": "Không tìm thấy buổi học."},
        )
    return sess


def get_sessions(
    db: Session,
    class_id: int,
    page: int = 1,
    page_size: int = 50,
    status_filter: SessionStatus | None = None,
) -> SessionListResponse:
    _get_class_or_404(db, class_id)
    query = db.query(SessionModel).filter(SessionModel.class_id == class_id)
    if status_filter:
        query = query.filter(SessionModel.status == status_filter)
    total = query.count()
    sessions = (
        query.order_by(SessionModel.date.asc(), SessionModel.start_time.asc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return SessionListResponse(
        items=[SessionOut.model_validate(s) for s in sessions],
        total=total,
        page=page,
        page_size=page_size,
    )


def update_session(
    db: Session,
    session_id: int,
    data: SessionUpdate,
    actor_id: int,
    ip: str | None = None,
) -> SessionOut:
    sess = _get_session_or_404(db, session_id)
    cls = _get_class_or_404(db, sess.class_id)

    if cls.status == ClassStatus.closed:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "CLASS_CLOSED", "message": "Lớp đã đóng, không thể sửa buổi."},
        )
    if sess.status != SessionStatus.scheduled:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "SESSION_NOT_EDITABLE",
                "message": f"Chỉ có thể sửa buổi ở trạng thái 'scheduled', hiện tại: {sess.status.value}.",
            },
        )

    new_date = data.date if data.date is not None else sess.date
    new_start = data.start_time if data.start_time is not None else sess.start_time
    new_end = data.end_time if data.end_time is not None else sess.end_time
    new_room = data.room.strip().upper() if data.room is not None else sess.room

    if new_start >= new_end:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": "INVALID_TIME", "message": "start_time phải trước end_time."},
        )

    # Kiểm tra xung đột (loại trừ chính buổi này)
    conflict_result = check_conflicts_for_sessions(
        db,
        proposed=[(new_date, new_start, new_end, new_room)],
        class_id=sess.class_id,
        lecturer_id=cls.lecturer_id,
        exclude_session_ids=[sess.id],
    )
    if conflict_result.has_conflict:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "SCHEDULE_CONFLICT",
                "message": "Thay đổi buổi học bị xung đột lịch.",
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

    old_values = {
        "date": str(sess.date),
        "start_time": str(sess.start_time),
        "end_time": str(sess.end_time),
        "room": sess.room,
    }
    sess.date = new_date
    sess.start_time = new_start
    sess.end_time = new_end
    sess.room = new_room

    log_action(
        db=db,
        user_id=actor_id,
        action="UPDATE_SESSION",
        entity="sessions",
        entity_id=str(sess.id),
        detail={
            "class_id": sess.class_id,
            "class_code": cls.code,
            "session_no": sess.session_no,
            "old": old_values,
            "new": {
                "date": str(new_date),
                "start_time": str(new_start),
                "end_time": str(new_end),
                "room": new_room,
            },
        },
        ip=ip,
    )
    db.commit()
    db.refresh(sess)
    return SessionOut.model_validate(sess)


def cancel_session(
    db: Session,
    session_id: int,
    actor_id: int,
    ip: str | None = None,
) -> SessionOut:
    sess = _get_session_or_404(db, session_id)
    cls = _get_class_or_404(db, sess.class_id)

    if cls.status == ClassStatus.closed:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "CLASS_CLOSED", "message": "Lớp đã đóng."},
        )
    if sess.status not in (SessionStatus.scheduled,):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "SESSION_NOT_CANCELLABLE",
                "message": f"Chỉ có thể hủy buổi ở trạng thái 'scheduled', hiện tại: {sess.status.value}.",
            },
        )

    old_status = sess.status.value
    sess.status = SessionStatus.cancelled

    log_action(
        db=db,
        user_id=actor_id,
        action="CANCEL_SESSION",
        entity="sessions",
        entity_id=str(sess.id),
        detail={
            "class_id": sess.class_id,
            "class_code": cls.code,
            "session_no": sess.session_no,
            "date": str(sess.date),
            "old_status": old_status,
            "new_status": "cancelled",
        },
        ip=ip,
    )
    db.commit()
    db.refresh(sess)
    return SessionOut.model_validate(sess)


def create_makeup_session(
    db: Session,
    class_id: int,
    data: SessionMakeupCreate,
    actor_id: int,
    ip: str | None = None,
) -> SessionOut:
    cls = _get_class_or_404(db, class_id)
    if cls.status == ClassStatus.closed:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "CLASS_CLOSED", "message": "Lớp đã đóng."},
        )

    room = data.room.strip().upper()

    # Kiểm tra xung đột
    conflict_result = check_conflicts_for_sessions(
        db,
        proposed=[(data.date, data.start_time, data.end_time, room)],
        class_id=class_id,
        lecturer_id=cls.lecturer_id,
    )
    if conflict_result.has_conflict:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "SCHEDULE_CONFLICT",
                "message": "Buổi bù bị xung đột lịch.",
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

    # Tính session_no tiếp theo
    max_no = db.query(func.max(SessionModel.session_no)).filter(SessionModel.class_id == class_id).scalar()
    next_no = (max_no or 0) + 1

    sess = SessionModel(
        class_id=class_id,
        schedule_id=None,  # buổi bù không có schedule
        session_no=next_no,
        date=data.date,
        start_time=data.start_time,
        end_time=data.end_time,
        room=room,
        status=SessionStatus.scheduled,
    )
    db.add(sess)
    db.flush()

    log_action(
        db=db,
        user_id=actor_id,
        action="CREATE_MAKEUP_SESSION",
        entity="sessions",
        entity_id=str(sess.id),
        detail={
            "class_id": class_id,
            "class_code": cls.code,
            "session_no": next_no,
            "date": str(data.date),
            "start_time": str(data.start_time),
            "end_time": str(data.end_time),
            "room": room,
        },
        ip=ip,
    )
    db.commit()
    db.refresh(sess)
    return SessionOut.model_validate(sess)
