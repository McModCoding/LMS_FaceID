"""Explicit safe configuration projection; never serialize Settings wholesale."""
from app.core.config import settings
from app.face.factory import get_engine


def system_info():
    engine = get_engine()
    return {"environment": settings.APP_ENV, "timezone": "Asia/Ho_Chi_Minh",
        "max_upload_mb": settings.MAX_UPLOAD_SIZE_MB,
        "access_token_minutes": settings.ACCESS_TOKEN_EXPIRE_MINUTES,
        "login_attempts": settings.LOGIN_MAX_ATTEMPTS, "login_lockout_minutes": settings.LOGIN_LOCKOUT_MINUTES,
        "exam_grace_seconds": settings.EXAM_GRACE_SECONDS,
        "attendance_edit_hours": settings.EDIT_AFTER_CLOSE_HOURS,
        "face_engine": engine.name, "face_ready": engine.is_ready,
        "demo_open_anytime": settings.DEV_ALLOW_OPEN_ANYTIME}
