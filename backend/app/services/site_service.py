"""Business logic for Site creation/listing. Kept separate from routes so
it can be unit-tested without spinning up FastAPI, and reused by both the
IT Admin and Inventory Manager route modules (they share identical site
permissions per the product spec)."""
import uuid
from typing import List

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.exceptions import ConflictError
from app.models.enums import SiteType
from app.models.site import Site
from app.models.user import User
from app.schemas.site import SiteCreate, SiteUpdate


def list_sites(db: Session) -> List[Site]:
    """
    Both IT_ADMIN and INVENTORY_MANAGER can see every site — there is no
    filtering here by design (per product spec: managers see "all
    inventories including master"). SITE_USER never calls this endpoint;
    routes enforce that via require_manager_or_admin.
    """
    return list(db.execute(select(Site).order_by(Site.name)).scalars().all())


def create_site(db: Session, payload: SiteCreate, created_by: User) -> Site:
    """
    Creates a site. When called by an Inventory Manager creating their
    OWN inventory (site_type=MANAGER_OWNED), `owned_by_user_id` is set to
    the creator so the frontend can visually distinguish "my inventory"
    from partner sites in the manager's dashboard.
    """
    site = Site(
        id=uuid.uuid4(),
        name=payload.name,
        code=payload.code,
        site_type=payload.site_type,
        owned_by_user_id=created_by.id if payload.site_type == SiteType.MANAGER_OWNED else None,
        contact_name=payload.contact_name,
        contact_email=payload.contact_email,
        contact_phone=payload.contact_phone,
        address=payload.address,
        created_by=created_by.id,
    )
    db.add(site)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        if "uq" in str(exc.orig).lower() or "unique" in str(exc.orig).lower():
            raise ConflictError(f"A site with code '{payload.code}' already exists.", field="code")
        raise
    db.refresh(site)
    return site


def update_site(db: Session, site: Site, payload: SiteUpdate) -> Site:
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(site, field, value)
    db.commit()
    db.refresh(site)
    return site
