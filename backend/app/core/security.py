"""
Custom authentication primitives: password hashing and JWT issuing/
verification. Replaces the earlier Supabase-JWKS-based verification —
this app now owns both sides of the token lifecycle (issuing AND
verifying), so tokens are signed with a single symmetric secret
(HS256) rather than verified against an external JWKS endpoint.

Two token types are minted, distinguished by a `type` claim so one can
never be silently accepted in place of the other:
  - "access": short-lived (ACCESS_TOKEN_EXPIRE_MINUTES), sent as a
    Bearer header on every API request.
  - "refresh": long-lived (REFRESH_TOKEN_EXPIRE_DAYS), stored ONLY in an
    httpOnly cookie client-side and, hashed, in the `refresh_tokens`
    table server-side (see app/models/refresh_token.py) so it can be
    revoked/rotated — a bare JWT can't be invalidated before it expires,
    which is why the DB-backed half exists at all.
"""
import hashlib
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Literal

import bcrypt
import jwt

from app.core.config import get_settings
from app.core.exceptions import UnauthorizedError

settings = get_settings()

TokenType = Literal["access", "refresh"]


# --- Password hashing ---------------------------------------------------
# Using the `bcrypt` library directly rather than passlib: passlib's
# bcrypt backend has had version-compatibility warnings with bcrypt>=4.1
# for a while and is effectively unmaintained — direct bcrypt use is
# simpler and has no such foot-gun. Bcrypt has a 72-byte input limit,
# handled by truncation guard below (matches bcrypt's own behavior, made
# explicit rather than silently relying on it).

_BCRYPT_MAX_BYTES = 72


def hash_password(plain_password: str) -> str:
    password_bytes = plain_password.encode("utf-8")[:_BCRYPT_MAX_BYTES]
    salt = bcrypt.gensalt(rounds=12)
    return bcrypt.hashpw(password_bytes, salt).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    password_bytes = plain_password.encode("utf-8")[:_BCRYPT_MAX_BYTES]
    try:
        return bcrypt.checkpw(password_bytes, hashed_password.encode("utf-8"))
    except (ValueError, TypeError):
        # Malformed hash (shouldn't happen, but never let a bad stored
        # hash turn into a 500 on login) — treat as a failed verification.
        return False


def validate_password_strength(password: str) -> None:
    """
    Minimum production-reasonable password policy. Raised as a plain
    ValueError so callers (auth_service) can wrap it in the app's
    ValidationAppError with a field name attached.
    """
    if len(password) < 8:
        raise ValueError("Password must be at least 8 characters long.")
    if not any(c.isupper() for c in password):
        raise ValueError("Password must contain at least one uppercase letter.")
    if not any(c.islower() for c in password):
        raise ValueError("Password must contain at least one lowercase letter.")
    if not any(c.isdigit() for c in password):
        raise ValueError("Password must contain at least one digit.")


# --- JWT access/refresh tokens -------------------------------------------

def _create_token(user_id: uuid.UUID, token_type: TokenType, expires_delta: timedelta) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "type": token_type,
        "iat": now,
        "exp": now + expires_delta,
        "jti": str(uuid.uuid4()),  # unique per token, useful for audit/logging even though revocation uses the hash
    }
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def create_access_token(user_id: uuid.UUID) -> str:
    return _create_token(user_id, "access", timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES))


def create_refresh_token(user_id: uuid.UUID) -> str:
    return _create_token(user_id, "refresh", timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS))


def decode_token(token: str, expected_type: TokenType) -> dict:
    """
    Verifies signature + expiry, and — critically — checks the `type`
    claim matches what the caller expects. Without this check, a leaked
    refresh token could be used directly as an access token (or vice
    versa), which would defeat the entire point of having two token
    types with different lifetimes and storage models.
    """
    try:
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise UnauthorizedError("Session expired. Please log in again.")
    except jwt.InvalidTokenError as exc:
        raise UnauthorizedError(f"Invalid authentication token: {exc}")

    if payload.get("type") != expected_type:
        raise UnauthorizedError(f"Expected a {expected_type} token.")
    if not payload.get("sub"):
        raise UnauthorizedError("Token missing subject claim.")

    return payload


# --- Opaque tokens for password reset / invite links ---------------------
# These are NOT JWTs — a random URL-safe string, stored server-side only
# as a SHA-256 hash (see PasswordResetToken model). This is deliberately
# simpler than a signed token: the DB row is the single source of truth
# for validity (used/expired/revoked), so there's no separate signature
# to verify and no risk of a self-contained JWT being "valid" per its own
# expiry claim while being stale relative to the DB.

def generate_opaque_token() -> str:
    return secrets.token_urlsafe(32)


def hash_opaque_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
