"""Dashboard stats route — one endpoint, role-scoped response (see schemas/dashboard.py)."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import require_any_role
from app.db.session import get_db
from app.models.user import User
from app.schemas.dashboard import DashboardStats
from app.services import dashboard_service

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/stats", response_model=DashboardStats)
def get_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_any_role),
):
    return dashboard_service.get_dashboard_stats(db, current_user)
