"""
Site routes. Per product spec, both IT_ADMIN and INVENTORY_MANAGER can
create and list sites — a manager's own inventory is created through this
same endpoint with site_type=manager_owned. SITE_USER has no access here
(they don't manage sites, only their own inventory's samples/reports).
"""
import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import require_manager_or_admin
from app.core.exceptions import NotFoundError
from app.db.session import get_db
from app.models.site import Site
from app.models.user import User
from app.schemas.site import SiteCreate, SiteRead, SiteUpdate
from app.services import site_service

router = APIRouter(prefix="/sites", tags=["sites"])


@router.get("", response_model=list[SiteRead])
def list_sites(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_manager_or_admin),
):
    return site_service.list_sites(db)


@router.post("", response_model=SiteRead, status_code=201)
def create_site(
    payload: SiteCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_manager_or_admin),
):
    return site_service.create_site(db, payload, created_by=current_user)


@router.patch("/{site_id}", response_model=SiteRead)
def update_site(
    site_id: uuid.UUID,
    payload: SiteUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_manager_or_admin),
):
    site = db.get(Site, site_id)
    if site is None:
        raise NotFoundError("Site not found.", field="site_id")
    return site_service.update_site(db, site, payload)
