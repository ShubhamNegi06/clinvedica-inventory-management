"""
User model.

Passwords are stored as bcrypt hashes (see app/core/security.py for
hash_password/verify_password) — this app now owns authentication
entirely; nothing is delegated to an external identity provider.
`id` is generated locally (uuid4) at creation time in app/services/
user_service.py, unlike the earlier Supabase-backed version where it had
to match an externally-issued UUID.
"""
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.models.enums import UserRole


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    email: Mapped[str] = mapped_column(String(320), unique=True, nullable=False, index=True)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(
        String(30), nullable=False, default=UserRole.SITE_USER
    )

    # Bcrypt hash — NEVER the plaintext password, and never returned in
    # any API response (UserRead schema deliberately omits this field).
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)

    # Required for SITE_USER (which site they belong to). NULL for
    # IT_ADMIN and INVENTORY_MANAGER, who are not scoped to one site.
    site_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sites.id", ondelete="SET NULL"), nullable=True
    )

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    created_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    site: Mapped[Optional["Site"]] = relationship(
        "Site", foreign_keys=[site_id], back_populates="users"
    )

    def __repr__(self) -> str:
        return f"<User {self.email} role={self.role}>"

