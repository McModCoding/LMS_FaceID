"""
routers/timetable.py
Thời khóa biểu: /me/timetable và /admin/timetable.
"""

from datetime import date, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db, require_admin
from app.models.user import User
from app.schemas.timetable import TimetableResponse
from app.services import timetable_service
from app.utils.clock import now_local

router = APIRouter(tags=["Timetable"])


@router.get("/me/timetable", response_model=TimetableResponse)
def my_timetable(
    from_date: date = Query(default_factory=lambda: now_local().date()),
    to_date: date = Query(default_factory=lambda: now_local().date() + timedelta(days=6)),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Trả thời khóa biểu cho người dùng hiện tại:
    - Giảng viên: lớp mình dạy.
    - Sinh viên: lớp mình đang enrolled.
    - Admin: tất cả (dùng /admin/timetable để lọc chi tiết hơn).
    """
    return timetable_service.get_my_timetable(db, current_user, from_date, to_date)


@router.get("/admin/timetable", response_model=TimetableResponse)
def admin_timetable(
    from_date: date = Query(default_factory=lambda: now_local().date()),
    to_date: date = Query(default_factory=lambda: now_local().date() + timedelta(days=6)),
    lecturer_id: int | None = None,
    department_id: int | None = None,
    room: str | None = None,
    class_id: int | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Admin xem thời khóa biểu theo bộ lọc."""
    return timetable_service.get_admin_timetable(
        db, from_date, to_date, lecturer_id=lecturer_id, department_id=department_id, room=room, class_id=class_id
    )
