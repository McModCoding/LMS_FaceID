"""Read audit data with Vietnam day boundaries and defensive redaction."""
import json
from datetime import UTC, date, datetime, time, timedelta

from fastapi import HTTPException

from app.models.audit import AuditLog
from app.models.user import User
from app.services.audit_service import sanitize_detail
from app.utils.clock import VN_TZ


def audit_detail(value):
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except ValueError:
            return {"message": "Chi tiết cũ không đúng định dạng."}
    if value is None:
        return None
    return sanitize_detail(value if isinstance(value, dict) else {"items": value})


def boundary(value: str | None, *, end=False):
    if not value:
        return None
    try:
        if len(value) == 10:
            local_date = date.fromisoformat(value) + (timedelta(days=1) if end else timedelta())
            return datetime.combine(local_date, time(), tzinfo=VN_TZ).astimezone(UTC).replace(tzinfo=None)
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            raise ValueError("missing timezone")
        return parsed.astimezone(UTC).replace(tzinfo=None)
    except ValueError:
        raise HTTPException(422, detail={"code": "INVALID_AUDIT_DATE", "message": "Nhập ngày YYYY-MM-DD hoặc thời điểm ISO có múi giờ."})


def list_logs(db, *, page, page_size, action=None, entity=None, performer=None, date_from=None, date_to=None):
    start, finish = boundary(date_from), boundary(date_to, end=True)
    if start and finish and start >= finish:
        raise HTTPException(422, detail={"code": "INVALID_DATE_RANGE", "message": "Ngày kết thúc phải bằng hoặc sau ngày bắt đầu."})
    query = db.query(AuditLog, User).outerjoin(User, AuditLog.user_id == User.id)
    if action:
        query = query.filter(AuditLog.action == action)
    if entity:
        query = query.filter(AuditLog.entity == entity)
    if performer:
        query = query.filter(User.username.contains(performer.strip(), autoescape=True))
    if start:
        query = query.filter(AuditLog.created_at >= start)
    if finish:
        query = query.filter(AuditLog.created_at < finish)
    total = query.count()
    items = [{"id": log.id, "user_id": log.user_id, "username": user.username if user else None,
        "action": log.action, "entity": log.entity, "entity_id": log.entity_id,
        "detail": audit_detail(log.detail), "ip": log.ip,
        "created_at": log.created_at.replace(tzinfo=UTC) if log.created_at.tzinfo is None else log.created_at}
        for log, user in query.order_by(AuditLog.created_at.desc(), AuditLog.id.desc()).offset((page - 1) * page_size).limit(page_size).all()]
    return {"items": items, "total": total, "page": page, "page_size": page_size}
