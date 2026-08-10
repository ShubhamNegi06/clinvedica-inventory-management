"""
Supabase JWT verification.

Supabase (new projects) signs access tokens with ES256 (asymmetric).
`python-jose` does not support ES256 against Supabase's JWKS correctly in
practice — this was a hard-won lesson from the v1 build — so we use PyJWT
with a JWKS client instead, exactly as proven out previously.

This module ONLY verifies the token and extracts claims. It does not know
about our `users` table — that lookup happens in app/api/deps.py, keeping
"is this token valid" separate from "who is this user in our system".
"""
from functools import lru_cache

import jwt
from jwt import PyJWKClient

from app.core.config import get_settings
from app.core.exceptions import UnauthorizedError

settings = get_settings()


@lru_cache
def _get_jwks_client() -> PyJWKClient:
    """
    Cached JWKS client. PyJWKClient internally caches keys and handles
    rotation, so we only need one instance per process, not per request.
    The `apikey` header is required by Supabase's JWKS endpoint even
    though the endpoint is otherwise "public".
    """
    return PyJWKClient(
        settings.SUPABASE_JWKS_URL,
        headers={"apikey": settings.SUPABASE_ANON_KEY},
    )


def decode_supabase_token(token: str) -> dict:
    """
    Verify signature, expiry, and audience of a Supabase-issued access token.
    Returns the decoded claims dict on success.

    Raises UnauthorizedError (never a raw jwt exception) so callers/routes
    never need to know about the PyJWT exception hierarchy.
    """
    try:
        signing_key = _get_jwks_client().get_signing_key_from_jwt(token)
        claims = jwt.decode(
            token,
            signing_key.key,
            algorithms=["ES256"],
            audience=settings.SUPABASE_JWT_AUDIENCE,
        )
        return claims
    except jwt.ExpiredSignatureError:
        raise UnauthorizedError("Session expired. Please log in again.")
    except jwt.InvalidTokenError as exc:
        raise UnauthorizedError(f"Invalid authentication token: {exc}")
    except Exception as exc:  # noqa: BLE001 — JWKS network/key errors etc.
        raise UnauthorizedError(f"Could not verify authentication token: {exc}")
