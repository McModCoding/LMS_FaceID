from collections.abc import Generator

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import SessionLocal
from app.models.user import User, UserRole

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_current_user(
    request: Request,
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail={"code": "INVALID_CREDENTIALS", "message": "Không thể xác thực danh tính người dùng."},
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        user_id_str: str = payload.get("sub")
        token_type: str = payload.get("type", "access")
        token_version: int | None = payload.get("token_version")
        if user_id_str is None or token_type != "access":
            raise credentials_exception
        user_id = int(user_id_str)
    except (JWTError, ValueError):
        raise credentials_exception from None

    user = db.query(User).filter(User.id == user_id).first()
    if not user or user.is_deleted or not user.is_active:
        raise credentials_exception

    # Kiểm tra token_version nếu có để đảm bảo token đã bị thu hồi sẽ bị từ chối
    if token_version is not None and user.token_version != token_version:
        raise credentials_exception

    # Check must_change_password
    path = request.url.path
    exempt_paths = ["/api/v1/auth/change-password", "/api/v1/auth/me"]
    if user.must_change_password and path not in exempt_paths:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "PASSWORD_CHANGE_REQUIRED",
                "message": "Bạn phải đổi mật khẩu lần đầu trước khi tiếp tục.",
            },
        )

    return user


def require_admin(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != UserRole.admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "FORBIDDEN", "message": "Bạn không có quyền thực hiện thao tác này."},
        )
    return current_user


def require_lecturer_or_admin(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role not in [UserRole.admin, UserRole.lecturer]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "FORBIDDEN", "message": "Bạn không có quyền thực hiện thao tác này."},
        )
    return current_user
