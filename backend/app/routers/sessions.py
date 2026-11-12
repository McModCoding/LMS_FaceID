"""
routers/sessions.py
Quản lý buổi học: PATCH, cancel, open, close, reopen, check-in.
"""

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db
from app.models.class_ import Class
from app.models.user import User, UserRole
from app.schemas.attendance import CheckInResult
from app.schemas.session import (
    SessionOpenRequest,
    SessionOut,
    SessionReopenRequest,
    SessionUpdate,
)
from app.services import session_service
from app.services.attendance_service import check_in_student as check_in_service
from app.services.session_lifecycle_service import (
    close_session as close_session_svc,
)
from app.services.session_lifecycle_service import (
    open_session as open_session_svc,
)
from app.services.session_lifecycle_service import (
    reopen_session as reopen_session_svc,
)
from app.utils.ip import get_client_ip

router = APIRouter(tags=["Sessions"])


def _require_admin_or_class_lecturer(db: Session, user: User, class_id: int) -> None:
    from fastapi import HTTPException

    if user.role == UserRole.admin:
        return
    if user.role == UserRole.lecturer:
        from app.models.lecturer import Lecturer

        lec = db.query(Lecturer).filter(
            Lecturer.user_id == user.id, Lecturer.is_deleted == False
        ).first()
        cls = db.query(Class).filter(Class.id == class_id, Class.is_deleted == False).first()
        if lec and cls and cls.lecturer_id == lec.id:
            return
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail={"code": "FORBIDDEN", "message": "Bạn không có quyền thực hiện thao tác này."},
    )


@router.patch("/sessions/{session_id}", response_model=SessionOut)
def update_session(
    session_id: int,
    data: SessionUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Sửa ngày/giờ/phòng của một buổi chưa mở (scheduled)."""
    sess = session_service._get_session_or_404(db, session_id)
    _require_admin_or_class_lecturer(db, current_user, sess.class_id)
    return session_service.update_session(db, session_id, data, current_user.id, get_client_ip(request))


@router.post("/sessions/{session_id}/cancel", response_model=SessionOut)
def cancel_session(
    session_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Hủy một buổi học (status -> cancelled)."""
    sess = session_service._get_session_or_404(db, session_id)
    _require_admin_or_class_lecturer(db, current_user, sess.class_id)
    return session_service.cancel_session(db, session_id, current_user.id, get_client_ip(request))


@router.post("/sessions/{session_id}/open", response_model=SessionOut)
def open_session(
    session_id: int,
    request: Request,
    data: SessionOpenRequest | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Mở buổi học (scheduled -> open). Admin ngoài cửa sổ phải có reason."""
    reason = data.reason if data else None
    return open_session_svc(db, session_id, current_user, reason, get_client_ip(request))


@router.post("/sessions/{session_id}/close", response_model=SessionOut)
def close_session(
    session_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Đóng buổi học (open -> closed)."""
    return close_session_svc(db, session_id, current_user, get_client_ip(request))


@router.post("/sessions/{session_id}/reopen", response_model=SessionOut)
def reopen_session(
    session_id: int,
    data: SessionReopenRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Mở lại buổi học đã đóng — chỉ Admin, bắt buộc reason."""
    return reopen_session_svc(db, session_id, current_user, data.reason, get_client_ip(request))


@router.post(
    "/sessions/{session_id}/attendance/{student_id}/check-in",
    response_model=CheckInResult,
)
def check_in_student(
    session_id: int,
    student_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Điểm danh nhanh thủ công cho một sinh viên (áp dụng theo mốc giờ)."""
    return check_in_service(db, session_id, student_id, current_user, get_client_ip(request))
