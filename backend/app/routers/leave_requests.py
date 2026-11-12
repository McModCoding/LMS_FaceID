"""
routers/leave_requests.py
Đơn xin vắng: sinh viên tạo/hủy, giảng viên/Admin duyệt.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db
from app.models.attendance import LeaveRequestStatus
from app.models.user import User, UserRole
from app.schemas.leave_request import (
    LeaveRequestCreate,
    LeaveRequestListResponse,
    LeaveRequestOut,
    LeaveRequestReview,
)
from app.services import leave_request_service
from app.utils.ip import get_client_ip

router = APIRouter(tags=["Leave Requests"])


def _get_student_or_403(db: Session, user: User):
    from app.models.student import Student

    if user.role != UserRole.student:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "FORBIDDEN", "message": "Chỉ sinh viên mới có thể thực hiện thao tác này."},
        )
    student = db.query(Student).filter(
        Student.user_id == user.id, Student.is_deleted == False
    ).first()
    if not student:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "STUDENT_NOT_FOUND", "message": "Không tìm thấy hồ sơ sinh viên."},
        )
    return student


# ──────────────────────── Sinh viên ─────────────────────────────────────────

@router.post("/sessions/{session_id}/leave-requests", response_model=LeaveRequestOut)
def create_leave_request(
    session_id: int,
    data: LeaveRequestCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Sinh viên gửi đơn xin vắng cho một buổi."""
    student = _get_student_or_403(db, current_user)
    # Ghi đè session_id từ path param
    data_with_session = LeaveRequestCreate(session_id=session_id, reason=data.reason)
    return leave_request_service.create_leave_request(
        db, student.id, data_with_session, get_client_ip(request)
    )


@router.delete("/leave-requests/{request_id}", response_model=LeaveRequestOut)
def cancel_leave_request(
    request_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Sinh viên hủy đơn xin vắng đang pending."""
    student = _get_student_or_403(db, current_user)
    return leave_request_service.cancel_leave_request(
        db, request_id, student.id, current_user.id, get_client_ip(request)
    )


@router.get("/me/leave-requests", response_model=LeaveRequestListResponse)
def get_my_leave_requests(
    class_id: int | None = Query(None),
    status_filter: LeaveRequestStatus | None = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Sinh viên xem danh sách đơn xin vắng của mình."""
    student = _get_student_or_403(db, current_user)
    return leave_request_service.get_my_leave_requests(db, student.id, page, page_size, class_id, status_filter)


# ──────────────────────── Giảng viên / Admin ────────────────────────────────

@router.get("/leave-requests", response_model=LeaveRequestListResponse)
def get_leave_requests(
    session_id: int | None = Query(None),
    class_id: int | None = Query(None),
    status_filter: LeaveRequestStatus | None = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Admin/Giảng viên xem danh sách đơn xin vắng."""
    if current_user.role not in (UserRole.admin, UserRole.lecturer):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "FORBIDDEN", "message": "Bạn không có quyền xem danh sách đơn xin vắng."},
        )
    return leave_request_service.get_leave_requests(
        db, current_user, session_id, class_id, status_filter, page, page_size
    )


@router.post("/leave-requests/{request_id}/review", response_model=LeaveRequestOut)
def review_leave_request(
    request_id: int,
    data: LeaveRequestReview,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Giảng viên/Admin duyệt hoặc từ chối đơn xin vắng."""
    if current_user.role not in (UserRole.admin, UserRole.lecturer):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "FORBIDDEN", "message": "Bạn không có quyền duyệt đơn."},
        )
    return leave_request_service.review_leave_request(
        db, request_id, current_user, data, get_client_ip(request)
    )
