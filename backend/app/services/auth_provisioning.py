"""
Supabase Auth account provisioning via the Admin API.

Kept deliberately separate from app/services/user_service.py: this module
knows about Supabase's REST shape; user_service.py knows about our domain
model. Neither should have to know about the other's internals.

Flow for "Create User" (IT Admin / Inventory Manager dashboards):
  1. provision_auth_user(...) creates the Supabase Auth account and sends
     an invite email with a redirect_to link pointing at our frontend's
     /set-password page. THIS redirect_to is the piece that was missing
     originally — without it, Supabase's invite link has nowhere useful
     to send the user, so they'd land on the invite confirmation with no
     way to actually set a password.
  2. The returned Supabase user ID is passed into user_service.create_user
     to create the corresponding local `users` row with role/site_id.

If step 2 fails after step 1 succeeds, the route wraps both in a
best-effort compensating action (delete the orphaned auth account) so we
don't leave a dangling Supabase Auth user with no local profile.

IMPORTANT — Supabase project setup required for this to work:
  The exact redirect URL (FRONTEND_URL + "/set-password") must be added
  to Supabase Dashboard -> Authentication -> URL Configuration ->
  Redirect URLs, or Supabase will silently ignore redirect_to and fall
  back to the site URL. This is a one-time manual step per environment
  (localhost for dev, your real domain for prod).
"""
import secrets
import string

import httpx

from app.core.config import get_settings
from app.core.exceptions import ConflictError, NotFoundError, StorageError

settings = get_settings()


def _admin_headers() -> dict:
    return {
        "apikey": settings.SUPABASE_SERVICE_ROLE_KEY,
        "Authorization": f"Bearer {settings.SUPABASE_SERVICE_ROLE_KEY}",
        "Content-Type": "application/json",
    }


def _set_password_redirect_url() -> str:
    return f"{settings.FRONTEND_URL.rstrip('/')}/set-password"


def provision_auth_user(email: str, full_name: str) -> str:
    """
    Creates a Supabase Auth user via invite (email_confirm required, user
    sets password themselves). Returns the new user's Supabase UUID.
    """
    url = f"{settings.SUPABASE_URL}/auth/v1/invite"
    body = {"email": email, "data": {"full_name": full_name}}

    try:
        response = httpx.post(
            url,
            headers=_admin_headers(),
            params={"redirect_to": _set_password_redirect_url()},
            json=body,
            timeout=15,
        )
    except httpx.HTTPError as exc:
        raise StorageError(f"Could not reach Supabase Auth to provision the account: {exc}")

    if response.status_code == 422 or "already been registered" in response.text.lower():
        raise ConflictError(f"A user with email '{email}' already exists in Supabase Auth.", field="email")
    if response.status_code >= 400:
        raise StorageError(f"Supabase Auth account provisioning failed ({response.status_code}): {response.text}")

    return response.json()["id"]


def delete_auth_user(user_id: str) -> None:
    """Deletes a Supabase Auth account entirely. Used both as a
    compensating action if local user-row creation fails, and as the
    real delete path for the 'Delete User' admin action."""
    url = f"{settings.SUPABASE_URL}/auth/v1/admin/users/{user_id}"
    try:
        response = httpx.delete(url, headers=_admin_headers(), timeout=15)
        if response.status_code >= 400 and response.status_code != 404:
            raise StorageError(f"Failed to delete the Supabase Auth account ({response.status_code}): {response.text}")
    except httpx.HTTPError as exc:
        raise StorageError(f"Could not reach Supabase Auth to delete the account: {exc}")


def send_password_reset_email(email: str) -> None:
    """
    Triggers Supabase's standard 'reset your password' email via the
    public recovery endpoint, with the same redirect_to as the invite
    flow so the link lands on our /set-password page (which handles
    both the invite and recovery cases identically — see the frontend
    page for why one page covers both).
    """
    url = f"{settings.SUPABASE_URL}/auth/v1/recover"
    try:
        response = httpx.post(
            url,
            headers={"apikey": settings.SUPABASE_ANON_KEY, "Content-Type": "application/json"},
            params={"redirect_to": _set_password_redirect_url()},
            json={"email": email},
            timeout=15,
        )
    except httpx.HTTPError as exc:
        raise StorageError(f"Could not reach Supabase Auth to send the reset email: {exc}")

    if response.status_code >= 400:
        raise StorageError(f"Failed to send password reset email ({response.status_code}): {response.text}")


def _generate_temp_password(length: int = 14) -> str:
    """Cryptographically random password, guaranteed to include letters, digits, and a symbol."""
    alphabet = string.ascii_letters + string.digits
    symbols = "!@#$%^&*"
    password = [secrets.choice(string.ascii_uppercase), secrets.choice(string.ascii_lowercase),
                secrets.choice(string.digits), secrets.choice(symbols)]
    password += [secrets.choice(alphabet) for _ in range(length - len(password))]
    secrets.SystemRandom().shuffle(password)
    return "".join(password)


def set_temporary_password(supabase_user_id: str) -> str:
    """
    Directly sets a new random password on the Supabase Auth account via
    the Admin API and returns it (plaintext, ONE TIME) so the calling
    admin can hand it to the user out-of-band (in person, phone, etc.).
    This does not touch email delivery at all — it's the "I need to give
    them access right now" alternative to send_password_reset_email.
    """
    temp_password = _generate_temp_password()
    url = f"{settings.SUPABASE_URL}/auth/v1/admin/users/{supabase_user_id}"
    try:
        response = httpx.put(
            url, headers=_admin_headers(), json={"password": temp_password}, timeout=15
        )
    except httpx.HTTPError as exc:
        raise StorageError(f"Could not reach Supabase Auth to set a temporary password: {exc}")

    if response.status_code == 404:
        raise NotFoundError("This user's Supabase Auth account could not be found.")
    if response.status_code >= 400:
        raise StorageError(f"Failed to set temporary password ({response.status_code}): {response.text}")

    return temp_password
