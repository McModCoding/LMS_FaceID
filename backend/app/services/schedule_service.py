"""
schedule_service.py
Tạo/sửa/xóa lịch học; sinh buổi học tự động.
"""

from __future__ import annotations

from datetime import date, timedelta

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.class_ import Class, ClassStatus
from app.models.schedule import Schedule
from app.models.semester import Semester
from app.models.session import Session as SessionModel
from app.models.session import SessionStatus
from app.schemas.schedule import ScheduleCreate, ScheduleUpdate
from app.services.audit_service import log_action
from app.services.conflict_service import check_conflicts_for_sessions


def _normalize_room(room: str) -> str:
    return room.strip().upper()


def _get_class_or_404(db: Session, class_id: int) -> Class:
    cls = db.query(Class).filter(Class.id == class_id, Class.is_deleted == False).first()
    if not cls:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "CLASS_NOT_FOUND", "message": "Không tìm thấy lớp học."},
        )
    return cls


def _get_semester_or_404(db: Session, semester_id: int) -> Semester:
    sem = db.query(Semester).filter(Semester.id == semester_id).first()
    if not sem:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "SEMESTER_NOT_FOUND", "message": "Không tìm thấy học kỳ."},
        )
    return sem


def _generate_session_dates(weekday: int, start_date: date, end_date: date) -> list[date]:
    """Sinh danh sách ngày học khớp thứ weekday (0=Thứ Hai) trong [start_date, end_date]."""
    # calendar.weekday() cũng dùng 0=Mon, 6=Sun — khớp với hệ thống
    dates = []
    current = start_date
    # Tìm ngày đầu tiên khớp weekday
    days_ahead = (weekday - current.weekday()) % 7
    current = current + timedelta(days=days_ahead)
    while current <= end_date:
        dates.append(current)
        current += timedelta(days=7)
    return dates


def _next_session_no(db: Session, class_id: int) -> int:
    """Số buổi tiếp theo (tăng dần, không đánh lại khi có buổi cancelled)."""
    from sqlalchemy import func as sqlfunc
    max_no = db.query(sqlfunc.max(SessionModel.session_no)).filter(SessionModel.class_id == class_id).scalar()
    return (max_no or 0) + 1


def get_schedules(db: Session, class_id: int) -> list[Schedule]:
    _get_class_or_404(db, class_id)
    return db.query(Schedule).filter(Schedule.class_id == class_id).order_by(Schedule.start_date).all()


def create_schedule(
    db: Session,
    class_id: int,
    data: ScheduleCreate,
    actor_id: int,
    ip: str | None = None,
) -> Schedule:
    cls = _get_class_or_404(db, class_id)

    if cls.status == ClassStatus.closed:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "CLASS_CLOSED", "message": "Lớp đã đóng, không thể thêm lịch."},
        )

    room = _normalize_room(data.room)

    # Validate khoảng ngày nằm trong học kỳ
    sem = _get_semester_or_404(db, cls.semester_id)
    if data.start_date < sem.start_date or data.end_date > sem.end_date:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "code": "DATE_OUT_OF_SEMESTER",
                "message": (
                    f"Khoảng ngày lịch học phải nằm trong học kỳ "
                    f"({sem.start_date} – {sem.end_date})."
                ),
            },
        )

    # Sinh danh sách ngày buổi học đề xuất
    proposed_dates = _generate_session_dates(data.weekday, data.start_date, data.end_date)
    if not proposed_dates:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "code": "NO_SESSIONS_GENERATED",
                "message": "Khoảng ngày không tạo ra buổi học nào khớp với thứ đã chọn.",
            },
        )

    proposed = [(d, data.start_time, data.end_time, room) for d in proposed_dates]

    # Kiểm tra xung đột
    conflict_result = check_conflicts_for_sessions(
        db,
        proposed=proposed,
        class_id=class_id,
        lecturer_id=cls.lecturer_id,
    )
    if conflict_result.has_conflict:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "SCHEDULE_CONFLICT",
                "message": "Lịch học bị xung đột. Vui lòng kiểm tra danh sách xung đột.",
                "details": {
                    "conflicts": [
                        {
                            "conflict_type": c.conflict_type,
                            "class_id": c.class_id,
                            "class_code": c.class_code,
                            "session_id": c.session_id,
                            "date": str(c.date),
                            "start_time": str(c.start_time),
                            "end_time": str(c.end_time),
                            "room": c.room,
                            "conflicting_entity": c.conflicting_entity,
                            "message": c.message,
                        }
                        for c in conflict_result.conflicts
                    ]
                },
            },
        )

    # Tạo schedule + sessions trong cùng giao dịch
    schedule = Schedule(
        class_id=class_id,
        weekday=data.weekday,
        start_time=data.start_time,
        end_time=data.end_time,
        room=room,
        start_date=data.start_date,
        end_date=data.end_date,
    )
    db.add(schedule)
    db.flush()  # lấy schedule.id

    # Tính session_no bắt đầu
    next_no = _next_session_no(db, class_id)
    # Sắp xếp theo ngày để đánh số đúng thứ tự
    for d in sorted(proposed_dates):
        sess = SessionModel(
            class_id=class_id,
            schedule_id=schedule.id,
            session_no=next_no,
            date=d,
            start_time=data.start_time,
            end_time=data.end_time,
            room=room,
            status=SessionStatus.scheduled,
        )
        db.add(sess)
        next_no += 1

    log_action(
        db=db,
        user_id=actor_id,
        action="CREATE_SCHEDULE",
        entity="schedules",
        entity_id=str(schedule.id),
        detail={
            "class_id": class_id,
            "class_code": cls.code,
            "weekday": data.weekday,
            "room": room,
            "start_date": str(data.start_date),
            "end_date": str(data.end_date),
            "sessions_created": len(proposed_dates),
        },
        ip=ip,
    )
    db.commit()
    db.refresh(schedule)
    return schedule


def update_schedule(
    db: Session,
    class_id: int,
    schedule_id: int,
    data: ScheduleUpdate,
    actor_id: int,
    ip: str | None = None,
) -> Schedule:
    cls = _get_class_or_404(db, class_id)
    if cls.status == ClassStatus.closed:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "CLASS_CLOSED", "message": "Lớp đã đóng, không thể sửa lịch."},
        )

    schedule = db.query(Schedule).filter(
        Schedule.id == schedule_id, Schedule.class_id == class_id
    ).first()
    if not schedule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "SCHEDULE_NOT_FOUND", "message": "Không tìm thấy lịch học."},
        )

    # Giá trị mới (giữ nguyên nếu không truyền)
    new_weekday = data.weekday if data.weekday is not None else schedule.weekday
    new_start = data.start_time if data.start_time is not None else schedule.start_time
    new_end = data.end_time if data.end_time is not None else schedule.end_time
    new_room = _normalize_room(data.room) if data.room is not None else schedule.room
    new_start_date = data.start_date if data.start_date is not None else schedule.start_date
    new_end_date = data.end_date if data.end_date is not None else schedule.end_date

    if new_start >= new_end:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": "INVALID_TIME", "message": "start_time phải trước end_time."},
        )
    if new_start_date > new_end_date:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": "INVALID_DATE", "message": "start_date phải trước hoặc bằng end_date."},
        )

    # Validate học kỳ
    sem = _get_semester_or_404(db, cls.semester_id)
    if new_start_date < sem.start_date or new_end_date > sem.end_date:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "code": "DATE_OUT_OF_SEMESTER",
                "message": f"Khoảng ngày phải nằm trong học kỳ ({sem.start_date} – {sem.end_date}).",
            },
        )

    # Tìm các buổi scheduled của lịch này (sẽ xóa và tạo lại)
    old_scheduled_sessions = (
        db.query(SessionModel)
        .filter(
            SessionModel.schedule_id == schedule_id,
            SessionModel.status == SessionStatus.scheduled,
        )
        .all()
    )
    old_session_ids = [s.id for s in old_scheduled_sessions]

    # Sinh buổi mới
    proposed_dates = _generate_session_dates(new_weekday, new_start_date, new_end_date)
    if not proposed_dates:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "code": "NO_SESSIONS_GENERATED",
                "message": "Khoảng ngày không tạo ra buổi học nào khớp với thứ đã chọn.",
            },
        )

    # Preserve processed history. Rebuilding a recurring schedule must not
    # recreate a closed/open occurrence, including when its weekday changes.
    preserved = db.query(SessionModel).filter(
        SessionModel.schedule_id == schedule_id,
        SessionModel.status != SessionStatus.scheduled,
    ).all()
    processed_dates = [s.date for s in preserved if s.status in (SessionStatus.open, SessionStatus.closed)]
    cutoff = max(processed_dates) if processed_dates else None
    preserved_dates = {s.date for s in preserved}
    proposed_dates = [d for d in proposed_dates if d not in preserved_dates and (cutoff is None or d > cutoff)]
    proposed = [(d, new_start, new_end, new_room) for d in proposed_dates]

    # Kiểm tra xung đột — loại trừ chính các buổi scheduled cũ sắp bị xóa
    conflict_result = check_conflicts_for_sessions(
        db,
        proposed=proposed,
        class_id=class_id,
        lecturer_id=cls.lecturer_id,
        exclude_session_ids=old_session_ids,
    )
    if conflict_result.has_conflict:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "SCHEDULE_CONFLICT",
                "message": "Lịch học bị xung đột. Vui lòng kiểm tra danh sách xung đột.",
                "details": {
                    "conflicts": [
                        {
                            "conflict_type": c.conflict_type,
                            "class_id": c.class_id,
                            "class_code": c.class_code,
                            "session_id": c.session_id,
                            "date": str(c.date),
                            "start_time": str(c.start_time),
                            "end_time": str(c.end_time),
                            "room": c.room,
                            "conflicting_entity": c.conflicting_entity,
                            "message": c.message,
                        }
                        for c in conflict_result.conflicts
                    ]
                },
            },
        )

    old_values = {
        "weekday": schedule.weekday,
        "start_time": str(schedule.start_time),
        "end_time": str(schedule.end_time),
        "room": schedule.room,
        "start_date": str(schedule.start_date),
        "end_date": str(schedule.end_date),
    }

    # Xóa buổi scheduled cũ
    for s in old_scheduled_sessions:
        db.delete(s)

    # Cập nhật schedule
    schedule.weekday = new_weekday
    schedule.start_time = new_start
    schedule.end_time = new_end
    schedule.room = new_room
    schedule.start_date = new_start_date
    schedule.end_date = new_end_date
    db.flush()

    # Tạo buổi mới, giữ nguyên session_no liên tục (session_no không đánh lại)
    next_no = _next_session_no(db, class_id)
    for d in sorted(proposed_dates):
        sess = SessionModel(
            class_id=class_id,
            schedule_id=schedule.id,
            session_no=next_no,
            date=d,
            start_time=new_start,
            end_time=new_end,
            room=new_room,
            status=SessionStatus.scheduled,
        )
        db.add(sess)
        next_no += 1

    log_action(
        db=db,
        user_id=actor_id,
        action="UPDATE_SCHEDULE",
        entity="schedules",
        entity_id=str(schedule.id),
        detail={
            "class_id": class_id,
            "class_code": cls.code,
            "old": old_values,
            "new": {
                "weekday": new_weekday,
                "start_time": str(new_start),
                "end_time": str(new_end),
                "room": new_room,
                "start_date": str(new_start_date),
                "end_date": str(new_end_date),
            },
            "sessions_deleted": len(old_session_ids),
            "sessions_created": len(proposed_dates),
        },
        ip=ip,
    )
    db.commit()
    db.refresh(schedule)
    return schedule


def delete_schedule(
    db: Session,
    class_id: int,
    schedule_id: int,
    actor_id: int,
    ip: str | None = None,
) -> None:
    cls = _get_class_or_404(db, class_id)
    if cls.status == ClassStatus.closed:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "CLASS_CLOSED", "message": "Lớp đã đóng, không thể xóa lịch."},
        )

    schedule = db.query(Schedule).filter(
        Schedule.id == schedule_id, Schedule.class_id == class_id
    ).first()
    if not schedule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "SCHEDULE_NOT_FOUND", "message": "Không tìm thấy lịch học."},
        )

    # Chỉ xóa buổi scheduled; không đụng open/closed
    scheduled_sessions = (
        db.query(SessionModel)
        .filter(
            SessionModel.schedule_id == schedule_id,
            SessionModel.status == SessionStatus.scheduled,
        )
        .all()
    )
    deleted_count = len(scheduled_sessions)
    for s in scheduled_sessions:
        db.delete(s)

    log_action(
        db=db,
        user_id=actor_id,
        action="DELETE_SCHEDULE",
        entity="schedules",
        entity_id=str(schedule.id),
        detail={
            "class_id": class_id,
            "class_code": cls.code,
            "weekday": schedule.weekday,
            "room": schedule.room,
            "sessions_deleted": deleted_count,
        },
        ip=ip,
    )
    db.delete(schedule)
    db.commit()
