"""Aggregate counts for the dashboard cards, scoped by role."""
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_accessible_site_ids
from app.models.enums import UserRole
from app.models.report import Report
from app.models.sample import Sample
from app.models.site import Site
from app.models.user import User
from app.schemas.dashboard import DashboardStats


def get_dashboard_stats(db: Session, current_user: User) -> DashboardStats:
    accessible = get_accessible_site_ids(current_user, db)

    sample_stmt = select(func.count()).select_from(Sample).where(Sample.is_deleted.is_(False))
    report_stmt = select(func.count()).select_from(Report)
    if accessible is not None:
        sample_stmt = sample_stmt.where(Sample.site_id.in_(accessible))
        report_stmt = report_stmt.where(Report.site_id.in_(accessible))

    total_samples = db.execute(sample_stmt).scalar_one()
    total_reports = db.execute(report_stmt).scalar_one()

    total_sites = None
    total_users = None
    if current_user.role in (UserRole.IT_ADMIN, UserRole.INVENTORY_MANAGER):
        total_sites = db.execute(select(func.count()).select_from(Site)).scalar_one()
        total_users = db.execute(select(func.count()).select_from(User)).scalar_one()

    return DashboardStats(
        total_sites=total_sites,
        total_users=total_users,
        total_samples=total_samples,
        total_reports=total_reports,
    )
