from datetime import UTC, datetime

from fastapi import HTTPException, status
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import (
    clear_attempts,
    create_access_token,
    create_refresh_token,
    get_password_hash,
    is_rate_limited,
    record_failed_attempt,
    verify_password,
)
from app.models.user import User
from app.schemas.auth import Token, UserRead
from app.services.audit_service import log_action


def login_user(db: Session, username: str, password: str, ip: str | None = None) -> Token:
    clean_username = username.lower().strip()
    rate_key = f"{ip or 'unknown'}:{clean_username}"

    if is_rate_limited(rate_key):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={"code": "TOO_MANY_REQUESTS", "message": "Quá nhiều lần đăng nhập sai. Vui lòng thử lại sau 15 phút."},
        )

    user = db.query(User).filter(User.username == clean_username, User.is_deleted == False).first()
    if not user or not verify_password(password, user.password_hash):
        record_failed_attempt(rate_key)
        # Ghi nhật ký đăng nhập thất bại
        log_action(
            db=db,
            user_id=user.id if user else None,
            action="LOGIN",
            entity="users",
            entity_id=str(user.id) if user else None,
            detail={
                "result": "failed",
                "username": clean_username,
                "reason": "Tên đăng nhập hoặc mật khẩu không chính xác",
                "summary": f"Đăng nhập thất bại: {clean_username} (Sai thông tin)",
            },
            ip=ip,
        )
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "INVALID_CREDENTIALS", "message": "Tên đăng nhập hoặc mật khẩu không chính xác."},
        )

    if not user.is_active:
        log_action(
            db=db,
            user_id=user.id,
            action="LOGIN",
            entity="users",
            entity_id=str(user.id),
            detail={
                "result": "failed",
                "username": clean_username,
                "reason": "Tài khoản đã bị khóa",
                "summary": f"Đăng nhập thất bại: {clean_username} (Tài khoản bị khóa)",
            },
            ip=ip,
        )
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "ACCOUNT_DISABLED", "message": "Tài khoản của bạn đã bị khóa."},
        )

    clear_attempts(rate_key)
    user.last_login_at = datetime.now(UTC)

    access_token = create_access_token(data={"sub": str(user.id), "role": user.role.value, "token_version": user.token_version})
    refresh_token = create_refresh_token(data={"sub": str(user.id), "role": user.role.value, "token_version": user.token_version})

    log_action(
        db=db,
        user_id=user.id,
        action="LOGIN",
        entity="users",
        entity_id=str(user.id),
        detail={
            "result": "success",
            "username": user.username,
            "summary": f"Đăng nhập thành công ({user.username})",
        },
        ip=ip,
    )
    db.commit()
    db.refresh(user)

    return Token(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        user=UserRead.model_validate(user),
    )


def refresh_token_service(db: Session, refresh_token: str) -> dict:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail={"code": "INVALID_TOKEN", "message": "Refresh token không hợp lệ hoặc đã hết hạn."},
    )
    try:
        payload = jwt.decode(refresh_token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        user_id_str: str = payload.get("sub")
        token_type: str = payload.get("type")
        token_version: int = payload.get("token_version")
        if user_id_str is None or token_type != "refresh":
            raise credentials_exception
        user_id = int(user_id_str)
    except (JWTError, ValueError):
        raise credentials_exception

    user = db.query(User).filter(User.id == user_id, User.is_deleted == False, User.is_active == True).first()
    if not user or user.token_version != token_version:
        raise credentials_exception

    new_access_token = create_access_token(data={"sub": str(user.id), "role": user.role.value, "token_version": user.token_version})
    return {"access_token": new_access_token, "token_type": "bearer"}


def change_password_service(db: Session, user_id: int, old_password: str, new_password: str, ip: str | None = None) -> Token:
    user = db.query(User).filter(User.id == user_id, User.is_deleted == False).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "USER_NOT_FOUND", "message": "Không tìm thấy người dùng."},
        )

    if not verify_password(old_password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "INVALID_OLD_PASSWORD", "message": "Mật khẩu cũ không chính xác."},
        )

    if old_password == new_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "SAME_PASSWORD", "message": "Mật khẩu mới không được trùng với mật khẩu cũ."},
        )

    if new_password.lower() == user.username.lower():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "PASSWORD_EQUALS_USERNAME", "message": "Mật khẩu mới không được trùng với tên đăng nhập."},
        )

    user.password_hash = get_password_hash(new_password)
    user.must_change_password = False
    user.token_version = (user.token_version or 1) + 1

    access_token = create_access_token(data={"sub": str(user.id), "role": user.role.value, "token_version": user.token_version})
    refresh_token = create_refresh_token(data={"sub": str(user.id), "role": user.role.value, "token_version": user.token_version})

    log_action(
        db=db,
        user_id=user.id,
        action="CHANGE_PASSWORD",
        entity="users",
        entity_id=str(user.id),
        detail={
            "username": user.username,
            "summary": f"Đổi mật khẩu thành công ({user.username})",
        },
        ip=ip,
    )
    db.commit()
    db.refresh(user)

    return Token(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        user=UserRead.model_validate(user),
    )
