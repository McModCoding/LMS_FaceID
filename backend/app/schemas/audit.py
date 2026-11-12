from datetime import datetime

from pydantic import BaseModel, ConfigDict


class AuditLogRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int | None = None
    username: str | None = None
    action: str
    entity: str
    entity_id: str | None = None
    detail: dict | None = None
    ip: str | None = None
    created_at: datetime

class AuditLogPaginatedResponse(BaseModel):
    items: list[AuditLogRead]
    total: int
    page: int
    page_size: int
