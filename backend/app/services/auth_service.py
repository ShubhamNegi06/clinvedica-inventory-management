"""
Core authentication business logic: login, token issuance, refresh-token
rotation/revocation, and password reset/invite token handling. This
replaces the old app/services/auth_provisioning.py, which delegated all
of this to Supabase's Admin API — everything here is local now (bcrypt
hashing + our own JWT issuing, no external identity provider).
"""
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.exceptions import (
    NotFoundError,
    UnauthorizedError,
    ValidationAppError,
)
from app.core.security import (
    create_access_token,
    create_refresh_token,
    generate_opaque_token,
    hash_opaque_token,
    hash_password,
    validate_password_strength,
    verify_password,
)
from app.models.password_reset_token import PasswordResetToken, TokenPurpose
from app.models.refresh_token import RefreshToken
from app.models.user import User

settings = get_settings()


# --- Login / token issuance ----------------------------------------------

def authenticate_user(db: Session, email: str, password: str) -> User:
    """
    Verifies credentials. Deliberately returns the SAME error message
    whether the email doesn't exist or the password is wrong — a
    different message for each would let an attacker enumerate valid
    emails by testing logins.
    """
    user = db.execute(select(User).where(User.email == email.lower().strip())).scalar_one_or_none()
    if user is None or not verify_password(password, user.hashed_password):
        raise UnauthorizedError("Incorrect email or password.")
    if not user.is_active:
        raise UnauthorizedError("This account has been deactivated. Contact your administrator.")
    return user


def issue_token_pair(db: Session, user: User) -> Tuple[str, str, datetime]:
    """
    Creates a new access+refresh token pair. The refresh token's hash is
    persisted so it can be looked up/revoked later; the raw refresh token
    is returned ONLY to be set as an httpOnly cookie by the route — it is
    never itself stored.

    Returns (access_token, raw_refresh_token, refresh_expires_at).
    """
    access_token = create_access_token(user.id)
    raw_refresh_token = create_refresh_token(user.id)

    expires_at = datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    db.add(
        RefreshToken(
            id=uuid.uuid4(),
            user_id=user.id,
            token_hash=hash_opaque_token(raw_refresh_token),
            expires_at=expires_at,
        )
    )
    db.commit()

    return access_token, raw_refresh_token, expires_at


def _get_valid_refresh_token_row(db: Session, raw_refresh_token: str) -> RefreshToken:
    from app.core.security import decode_token

    # Verify the JWT signature/expiry/type first — cheap check before
    # touching the DB, and it rejects a forged token outright.
    payload = decode_token(raw_refresh_token, expected_type="refresh")
    user_id = uuid.UUID(payload["sub"])

    token_hash = hash_opaque_token(raw_refresh_token)
    row = db.execute(
        select(RefreshToken).where(RefreshToken.token_hash == token_hash, RefreshToken.user_id == user_id)
    ).scalar_one_or_none()

    if row is None:
        raise UnauthorizedError("Refresh token not recognized. Please log in again.")
    if row.revoked_at is not None:
        # Reuse of an already-rotated-out token — could be legitimate
        # double-submission, but treated as invalid rather than silently
        # re-issuing, since a rotated token being reused is exactly the
        # signal of possible token theft that rotation exists to surface.
        raise UnauthorizedError("This session has already been used. Please log in again.")
    if row.expires_at < datetime.now(timezone.utc):
        raise UnauthorizedError("Session expired. Please log in again.")

    return row


def refresh_token_pair(db: Session, raw_refresh_token: str) -> Tuple[str, str, datetime, User]:
    """
    Validates the presented refresh token, rotates it (revokes the old
    one, issues a new one), and returns a fresh access+refresh pair.
    Rotation on every use is what makes "logout everywhere" and theft
    detection meaningful rather than cosmetic.
    """
    old_row = _get_valid_refresh_token_row(db, raw_refresh_token)

    user = db.get(User, old_row.user_id)
    if user is None or not user.is_active:
        raise UnauthorizedError("Account no longer available.")

    access_token, new_raw_refresh_token, expires_at = issue_token_pair(db, user)

    # Look up the just-created row to link the rotation chain, then
    # revoke the old one.
    new_hash = hash_opaque_token(new_raw_refresh_token)
    new_row = db.execute(select(RefreshToken).where(RefreshToken.token_hash == new_hash)).scalar_one()
    old_row.revoked_at = datetime.now(timezone.utc)
    old_row.replaced_by_id = new_row.id
    db.commit()

    return access_token, new_raw_refresh_token, expires_at, user


def revoke_refresh_token(db: Session, raw_refresh_token: str) -> None:
    """Logout: revokes the single presented refresh token. Never raises
    if the token is already invalid/missing — logging out should always
    succeed from the client's point of view."""
    try:
        row = _get_valid_refresh_token_row(db, raw_refresh_token)
    except UnauthorizedError:
        return
    row.revoked_at = datetime.now(timezone.utc)
    db.commit()


def revoke_all_refresh_tokens_for_user(db: Session, user_id: uuid.UUID) -> None:
    """
    Revokes every active refresh token for a user — used after a
    password reset/change and after an admin deletes a user, so old
    sessions can't keep working with credentials that are no longer
    current.
    """
    now = datetime.now(timezone.utc)
    rows = db.execute(
        select(RefreshToken).where(RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None))
    ).scalars()
    for row in rows:
        row.revoked_at = now
    db.commit()


# --- Password reset / invite tokens --------------------------------------

def create_password_reset_token(db: Session, user: User, purpose: TokenPurpose) -> str:
    """
    Creates a new opaque, single-use, expiring token and returns the
    RAW value (only used to build the email link — the DB stores only
    its hash). Expiry differs by purpose: invite links live longer
    (INVITE_TOKEN_EXPIRE_HOURS) since a new hire might not check email
    immediately; reset links are short (PASSWORD_RESET_TOKEN_EXPIRE_MINUTES)
    since account-recovery links are a more sensitive artifact.
    """
    raw_token = generate_opaque_token()
    expire_delta = (
        timedelta(hours=settings.INVITE_TOKEN_EXPIRE_HOURS)
        if purpose == TokenPurpose.INVITE
        else timedelta(minutes=settings.PASSWORD_RESET_TOKEN_EXPIRE_MINUTES)
    )

    db.add(
        PasswordResetToken(
            id=uuid.uuid4(),
            user_id=user.id,
            token_hash=hash_opaque_token(raw_token),
            purpose=purpose,
            expires_at=datetime.now(timezone.utc) + expire_delta,
        )
    )
    db.commit()
    return raw_token


def consume_password_reset_token(db: Session, raw_token: str, new_password: str) -> User:
    """
    Validates the token (exists, not used, not expired), sets the new
    password, marks the token used, and revokes all of the user's
    existing refresh tokens — a password reset should force re-login on
    every other device/session, not just the one performing the reset.
    """
    try:
        validate_password_strength(new_password)
    except ValueError as exc:
        raise ValidationAppError(str(exc), field="password")

    token_hash = hash_opaque_token(raw_token)
    row = db.execute(
        select(PasswordResetToken).where(PasswordResetToken.token_hash == token_hash)
    ).scalar_one_or_none()

    if row is None:
        raise NotFoundError("This link is invalid.", field="token")
    if row.used_at is not None:
        raise ValidationAppError("This link has already been used. Request a new one.", field="token")
    if row.expires_at < datetime.now(timezone.utc):
        raise ValidationAppError("This link has expired. Request a new one.", field="token")

    user = db.get(User, row.user_id)
    if user is None:
        raise NotFoundError("Account not found.")

    user.hashed_password = hash_password(new_password)
    row.used_at = datetime.now(timezone.utc)
    db.commit()

    revoke_all_refresh_tokens_for_user(db, user.id)
    return user


def set_temporary_password(db: Session, user: User) -> str:
    """
    Immediately sets a random password on the account and returns it
    ONCE (plaintext) for the calling admin to share out-of-band. Also
    revokes existing sessions, same reasoning as a password reset.
    """
    temp_password = generate_opaque_token()[:16]  # URL-safe chars, plenty of entropy for a one-time password
    user.hashed_password = hash_password(temp_password)
    db.commit()
    revoke_all_refresh_tokens_for_user(db, user.id)
    return temp_password
