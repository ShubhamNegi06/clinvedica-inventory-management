"""
RefreshToken model.

Refresh tokens are stored SERVER-SIDE (hashed, never plaintext) so we can
revoke them — a stateless JWT alone can't be invalidated before its
natural expiry, which breaks "logout" and "revoke on password reset" as
real security properties rather than UI theater.

Rotation: every time a refresh token is used at POST /auth/refresh, it is
revoked and a new one issued (see app/services/auth_service.py). This
means a stolen refresh token that gets used by an attacker AND the real
user both trying to use the same token after one of them already rotated
it will fail for the second user — a detectable signal of token theft,
not just a nice-to-have.
"""
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # SHA-256 hex digest of the raw refresh token — never store the raw
    # token itself, same principle as password hashing.
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)

    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Set when this token was rotated out in favor of a newer one — lets
    # us trace a rotation chain if we ever need to investigate token theft.
    replaced_by_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("refresh_tokens.id", ondelete="SET NULL"), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    def __repr__(self) -> str:
        return f"<RefreshToken user={self.user_id} revoked={self.revoked_at is not None}>"
