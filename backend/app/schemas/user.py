from pydantic import BaseModel


class UserStatusUpdate(BaseModel):
    is_active: bool

class ResetPasswordResponse(BaseModel):
    user_id: int
    username: str
    temp_password: str
