from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.security import generate_temp_password, get_password_hash
from app.models.user import User
from app.schemas.user import ResetPasswordResponse
from app.services.audit_service import log_action


def toggle_user_status(
    db: Session,
    user_id: int,
    is_active: bool,
    admin_id: int,
    ip: str | None = None,
) -> User:
    user = db.query(User).filter(User.id == user_id, User.is_deleted == False).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "USER_NOT_FOUND", "message": "Không tìm thấy người dùng."},
        )

    old_status = user.is_active
    user.is_active = is_active
    # Thu hồi token cũ bằng cách tăng token_version
    user.token_version = (user.token_version or 1) + 1

    action_label = "Mở khóa" if is_active else "Khóa"
    status_label_old = "Hoạt động" if old_status else "Bị khóa"
    status_label_new = "Hoạt động" if is_active else "Bị khóa"

    log_action(
        db=db,
        user_id=admin_id,
        action="TOGGLE_USER_STATUS",
        entity="users",
        entity_id=str(user.id),
        detail={
            "target_username": user.username,
            "old_is_active": old_status,
            "new_is_active": is_active,
            "summary": f"{action_label} tài khoản {user.username} ({status_label_old} → {status_label_new})",
        },
        ip=ip,
    )
    db.commit()
    db.refresh(user)
    return user


def reset_password(
    db: Session,
    user_id: int,
    admin_id: int,
    ip: str | None = None,
) -> ResetPasswordResponse:
    user = db.query(User).filter(User.id == user_id, User.is_deleted == False).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "USER_NOT_FOUND", "message": "Không tìm thấy người dùng."},
        )

    temp_password = generate_temp_password(10)
    user.password_hash = get_password_hash(temp_password)
    user.must_change_password = True
    user.token_version = (user.token_version or 1) + 1

    # Tuyệt đối KHÔNG ghi mật khẩu hoặc hash vào detail nhật ký
    log_action(
        db=db,
        user_id=admin_id,
        action="RESET_PASSWORD",
        entity="users",
        entity_id=str(user.id),
        detail={
            "target_username": user.username,
            "summary": f"Reset mật khẩu tạm cho tài khoản {user.username}",
        },
        ip=ip,
    )
    db.commit()
    db.refresh(user)

    return ResetPasswordResponse(
        user_id=user.id,
        username=user.username,
        temp_password=temp_password,
    )
