"""
Site model.

A "Site" represents any inventory-holding unit in the system:
  - a real hospital/pathology lab (SiteType.PARTNER_SITE), or
  - an Inventory Manager's own inventory (SiteType.MANAGER_OWNED).

Both are structurally identical (same fields, same permission surface for
CRUD on samples/reports underneath them). This means "Master Inventory"
in the dashboards is never a separate table — it is simply an aggregate
query across ALL sites, which keeps the schema simple and avoids data
duplication between "site inventory" and "master inventory".
"""
import uuid
from datetime import datetime
from typing import List, Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.models.enums import SiteType


class Site(Base):
    __tablename__ = "sites"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    # Short unique code used in sample_id prefixes / filtering, e.g. "AIIMS-DEL"
    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)

    site_type: Mapped[SiteType] = mapped_column(String(30), nullable=False, default=SiteType.PARTNER_SITE)

    # Set only when site_type == MANAGER_OWNED — identifies which manager
    # this personal inventory belongs to. NULL for partner sites.
    owned_by_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    contact_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    contact_email: Mapped[Optional[str]] = mapped_column(String(320), nullable=True)
    contact_phone: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    address: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    created_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    users: Mapped[List["User"]] = relationship(
        "User", foreign_keys="User.site_id", back_populates="site"
    )
    samples: Mapped[List["Sample"]] = relationship(
        "Sample", back_populates="site", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Site {self.code} ({self.site_type})>"
