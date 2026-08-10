"""
Supabase Auth account provisioning via the Admin API.

Kept deliberately separate from app/services/user_service.py: this module
knows about Supabase's REST shape; user_service.py knows about our domain
model. Neither should have to know about the other's internals.

Flow for "Create User" (IT Admin / Inventory Manager dashboards):
  1. provision_auth_user(...) creates the Supabase Auth account and sends
     an invite email (user sets their own password via the emailed link —
     we never handle raw passwords).
  2. The returned Supabase user ID is passed into user_service.create_user
     to create the corresponding local `users` row with role/site_id.

If step 2 fails after step 1 succeeds, the route wraps both in a
best-effort compensating action (delete the orphaned auth account) so we
don't leave a dangling Supabase Auth user with no local profile.
"""
import httpx

from app.core.config import get_settings
from app.core.exceptions import ConflictError, StorageError

settings = get_settings()


def _admin_headers() -> dict:
    return {
        "apikey": settings.SUPABASE_SERVICE_ROLE_KEY,
        "Authorization": f"Bearer {settings.SUPABASE_SERVICE_ROLE_KEY}",
        "Content-Type": "application/json",
    }


def provision_auth_user(email: str, full_name: str) -> str:
    """
    Creates a Supabase Auth user via invite (email_confirm required, user
    sets password themselves). Returns the new user's Supabase UUID.
    """
    url = f"{settings.SUPABASE_URL}/auth/v1/invite"
    body = {"email": email, "data": {"full_name": full_name}}

    try:
        response = httpx.post(url, headers=_admin_headers(), json=body, timeout=15)
    except httpx.HTTPError as exc:
        raise StorageError(f"Could not reach Supabase Auth to provision the account: {exc}")

    if response.status_code == 422 or "already been registered" in response.text.lower():
        raise ConflictError(f"A user with email '{email}' already exists in Supabase Auth.", field="email")
    if response.status_code >= 400:
        raise StorageError(f"Supabase Auth account provisioning failed ({response.status_code}): {response.text}")

    return response.json()["id"]


def delete_auth_user(user_id: str) -> None:
    """Compensating action if local user-row creation fails after the auth account was created."""
    url = f"{settings.SUPABASE_URL}/auth/v1/admin/users/{user_id}"
    try:
        httpx.delete(url, headers=_admin_headers(), timeout=15)
    except httpx.HTTPError:
        # Best-effort cleanup only — the primary error to the caller
        # already reflects the real failure; don't mask it with this.
        pass
