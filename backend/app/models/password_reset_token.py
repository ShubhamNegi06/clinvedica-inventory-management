"""
PasswordResetToken model.

Covers two purposes with one mechanism:
  - INVITE: sent when an admin creates a new user (no usable password
    set yet) — the email says "set your password", not "reset it".
  - RESET: sent via "forgot password" or an admin's "send password
    reset" action on an existing account.

Both are functionally identical (a single-use, expiring, emailed link
that lets someone set a new password), so one table with a `purpose`
column avoids duplicating the token-generation/validation logic for what
is otherwise the same flow. The email content differs by purpose; the
security mechanics do not.

Tokens are stored hashed (SHA-256), exactly like refresh tokens — the
plaintext token only ever exists in memory long enough to build the
email link, never persisted.
"""
import enum
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class TokenPurpose(str, enum.Enum):
    INVITE = "invite"
    RESET = "reset"


class PasswordResetToken(Base):
    __tablename__ = "password_reset_tokens"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )

    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    purpose: Mapped[TokenPurpose] = mapped_column(String(20), nullable=False, default=TokenPurpose.RESET)

    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    def __repr__(self) -> str:
        return f"<PasswordResetToken user={self.user_id} purpose={self.purpose} used={self.used_at is not None}>"
