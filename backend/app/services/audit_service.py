from typing import Any

from sqlalchemy.orm import Session

from app.models.audit import AuditLog

SENSITIVE_KEYS = {
    "password",
    "old_password",
    "new_password",
    "temp_password",
    "password_hash",
    "token",
    "access_token",
    "refresh_token",
    "authorization",
    "secret_key",
    "db_password",
    "database_url",
    "api_key",
    "embedding",
    "image_path",
}


def sanitize_detail(data: Any) -> Any:
    if isinstance(data, dict):
        sanitized = {}
        for k, v in data.items():
            normalized = k.lower().replace("-", "_")
            if normalized in SENSITIVE_KEYS or normalized.endswith(("_password", "_secret", "_token", "_embedding")):
                sanitized[k] = "[REDACTED]"
            else:
                sanitized[k] = sanitize_detail(v)
        return sanitized
    elif isinstance(data, list):
        return [sanitize_detail(item) for item in data]
    return data


def log_action(
    db: Session,
    user_id: int | None,
    action: str,
    entity: str,
    entity_id: str | None = None,
    detail: dict | None = None,
    ip: str | None = None,
) -> AuditLog:
    """
    Thêm bản ghi nhật ký vào session hiện tại.
    Bảo đảm cùng giao dịch với thay đổi dữ liệu (Caller thực hiện db.commit() hoặc rollback).
    """
    sanitized = sanitize_detail(detail) if detail else None
    audit = AuditLog(
        user_id=user_id,
        action=action,
        entity=entity,
        entity_id=str(entity_id) if entity_id is not None else None,
        detail=sanitized,
        ip=ip,
    )
    db.add(audit)
    return audit
