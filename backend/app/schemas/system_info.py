from pydantic import BaseModel


class SystemInfoOut(BaseModel):
    environment: str
    timezone: str
    max_upload_mb: int
    access_token_minutes: int
    login_attempts: int
    login_lockout_minutes: int
    exam_grace_seconds: int
    attendance_edit_hours: int
    face_engine: str
    face_ready: bool
    demo_open_anytime: bool
