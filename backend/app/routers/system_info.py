from fastapi import APIRouter, Depends

from app.core.deps import require_admin
from app.models.user import User
from app.schemas.system_info import SystemInfoOut
from app.services.system_info_service import system_info

router = APIRouter(tags=["System configuration"])


@router.get("/admin/system-info", response_model=SystemInfoOut)
def read(admin: User = Depends(require_admin)):
    return system_info()
