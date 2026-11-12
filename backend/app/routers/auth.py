from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db
from app.models.user import User
from app.schemas.auth import (
    ChangePasswordRequest,
    LoginRequest,
    RefreshTokenRequest,
    Token,
    UserRead,
)
from app.services.auth_service import (
    change_password_service,
    login_user,
    refresh_token_service,
)
from app.utils.ip import get_client_ip

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=Token)
def login(data: LoginRequest, request: Request, db: Session = Depends(get_db)):
    client_ip = get_client_ip(request)
    return login_user(db, username=data.username, password=data.password, ip=client_ip)


@router.post("/refresh")
def refresh(data: RefreshTokenRequest, db: Session = Depends(get_db)):
    return refresh_token_service(db, refresh_token=data.refresh_token)


@router.post("/change-password", response_model=Token)
def change_password(
    data: ChangePasswordRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    client_ip = get_client_ip(request)
    return change_password_service(
        db=db,
        user_id=current_user.id,
        old_password=data.old_password,
        new_password=data.new_password,
        ip=client_ip,
    )


@router.get("/me", response_model=UserRead)
def get_me(current_user: User = Depends(get_current_user)):
    return current_user
