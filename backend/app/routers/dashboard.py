from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db
from app.models.user import User
from app.schemas.dashboard import DashboardOut
from app.services.dashboard_service import dashboard

router = APIRouter(tags=["Dashboard"])


@router.get("/me/dashboard", response_model=DashboardOut)
def read(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return dashboard(db, user)
