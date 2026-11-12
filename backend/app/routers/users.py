from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.core.deps import get_db, require_admin
from app.models.user import User
from app.schemas.user import ResetPasswordResponse, UserStatusUpdate
from app.services.user_service import reset_password, toggle_user_status
from app.utils.ip import get_client_ip

router = APIRouter(prefix="/users", tags=["users"])


@router.patch("/{user_id}/status")
def update_user_status_endpoint(
    user_id: int,
    data: UserStatusUpdate,
    request: Request,
    db: Session = Depends(get_db),
    admin_user: User = Depends(require_admin),
):
    client_ip = get_client_ip(request)
    user = toggle_user_status(
        db=db,
        user_id=user_id,
        is_active=data.is_active,
        admin_id=admin_user.id,
        ip=client_ip,
    )
    return {
        "message": f"Tài khoản {user.username} đã được {'mở khóa' if user.is_active else 'khóa'}.",
        "is_active": user.is_active,
    }


@router.post("/{user_id}/reset-password", response_model=ResetPasswordResponse)
def reset_password_endpoint(
    user_id: int,
    request: Request,
    db: Session = Depends(get_db),
    admin_user: User = Depends(require_admin),
):
    client_ip = get_client_ip(request)
    return reset_password(
        db=db,
        user_id=user_id,
        admin_id=admin_user.id,
        ip=client_ip,
    )
