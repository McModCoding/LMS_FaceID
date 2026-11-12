from datetime import datetime

from pydantic import BaseModel, ConfigDict, field_validator

from app.models.user import UserRole


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    email: str
    role: UserRole
    is_active: bool
    must_change_password: bool
    last_login_at: datetime | None = None
    created_at: datetime

class LoginRequest(BaseModel):
    username: str
    password: str

class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: UserRead

class RefreshTokenRequest(BaseModel):
    refresh_token: str

class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str

    @field_validator("new_password")
    @classmethod
    def validate_new_password(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Mật khẩu mới phải có ít nhất 8 ký tự.")
        if not any(c.isalpha() for c in v) or not any(c.isdigit() for c in v):
            raise ValueError("Mật khẩu mới phải bao gồm cả chữ cái và chữ số.")
        return v
