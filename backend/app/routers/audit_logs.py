from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.deps import get_db, require_admin
from app.models.user import User
from app.schemas.audit import AuditLogPaginatedResponse
from app.services.audit_query_service import list_logs

router = APIRouter(prefix="/audit-logs", tags=["audit-logs"])


@router.get("", response_model=AuditLogPaginatedResponse)
def list_audit_logs(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    action: str | None = Query(None),
    entity: str | None = Query(None),
    performer: str | None = Query(None),
    date_from: str | None = Query(None),
    date_to: str | None = Query(None),
    db: Session = Depends(get_db),
    admin_user: User = Depends(require_admin),
):
    return list_logs(db, page=page, page_size=page_size, action=action, entity=entity,
                     performer=performer, date_from=date_from, date_to=date_to)
