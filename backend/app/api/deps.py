"""
Shared FastAPI dependencies: authentication + role-based access control
(RBAC).

Design principle: permission logic lives HERE, once, as reusable
dependencies — never as scattered `if current_user.role == "..."` checks
inside individual route handlers. Every route declares what it needs
(`require_roles(...)`, `require_site_access(...)`) and the dependency
either returns the resolved object or raises a structured AppError.
"""
import uuid
from typing import Callable, Iterable

from fastapi import Depends, Header
from sqlalchemy.orm import Session

from app.core.exceptions import PermissionDeniedError, UnauthorizedError
from app.core.security import decode_supabase_token
from app.db.session import get_db
from app.models.enums import UserRole
from app.models.site import Site
from app.models.user import User


def get_bearer_token(authorization: str = Header(default=None)) -> str:
    """Extract the raw bearer token from the Authorization header."""
    if not authorization or not authorization.lower().startswith("bearer "):
        raise UnauthorizedError("Missing or malformed Authorization header.")
    return authorization.split(" ", 1)[1].strip()


def get_current_user(
    token: str = Depends(get_bearer_token),
    db: Session = Depends(get_db),
) -> User:
    """
    Resolve the authenticated Supabase JWT into our own `User` row.

    A verified token but no matching local user (e.g. deprovisioned, or
    Supabase Auth account created but never provisioned in our `users`
    table) is treated as unauthorized, not as an anonymous/guest user —
    this app has no anonymous access anywhere.
    """
    claims = decode_supabase_token(token)
    user_id = claims.get("sub")
    if not user_id:
        raise UnauthorizedError("Token missing subject claim.")

    user = db.get(User, uuid.UUID(user_id))
    if user is None:
        raise UnauthorizedError("No matching user account found for this session.")
    if not user.is_active:
        raise PermissionDeniedError("This account has been deactivated. Contact your administrator.")
    return user


def require_roles(*allowed_roles: UserRole) -> Callable[[User], User]:
    """
    Dependency factory: `Depends(require_roles(UserRole.IT_ADMIN))`.
    Returns the current user if their role is in `allowed_roles`, else 403.
    """

    def _checker(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in {r.value if isinstance(r, UserRole) else r for r in allowed_roles}:
            raise PermissionDeniedError(
                f"This action requires one of the following roles: "
                f"{', '.join(r.value if isinstance(r, UserRole) else r for r in allowed_roles)}."
            )
        return current_user

    return _checker


def get_accessible_site_ids(current_user: User, db: Session) -> Iterable[uuid.UUID] | None:
    """
    Returns the set of site IDs the current user may read/write, or None
    to mean "all sites" (IT_ADMIN and INVENTORY_MANAGER both see every
    inventory, per the product spec — a manager's own inventory is just
    one more Site among the ones they can already see).

    SITE_USER is restricted to exactly their own site.
    """
    if current_user.role in (UserRole.IT_ADMIN, UserRole.INVENTORY_MANAGER):
        return None  # no restriction — caller should not filter by site_id
    if current_user.role == UserRole.SITE_USER:
        if current_user.site_id is None:
            raise PermissionDeniedError("Your account is not linked to a site. Contact your administrator.")
        return {current_user.site_id}
    raise PermissionDeniedError("Unrecognized role.")


def assert_site_access(site_id: uuid.UUID, current_user: User, db: Session) -> Site:
    """
    Fetches a Site and verifies the current user may access it. Raises
    PermissionDeniedError (site users on a foreign site) or NotFoundError
    (via caller) as appropriate. Use this for single-resource routes
    (e.g. POST /sites/{site_id}/samples) rather than re-deriving the
    accessible-site-set logic inline.
    """
    accessible = get_accessible_site_ids(current_user, db)
    if accessible is not None and site_id not in accessible:
        raise PermissionDeniedError("You do not have access to this site's inventory.")

    site = db.get(Site, site_id)
    if site is None:
        from app.core.exceptions import NotFoundError

        raise NotFoundError("Site not found.", field="site_id")
    return site


# --- Convenience dependency instances for common role combinations ---
require_it_admin = require_roles(UserRole.IT_ADMIN)
require_manager_or_admin = require_roles(UserRole.IT_ADMIN, UserRole.INVENTORY_MANAGER)
require_any_role = require_roles(UserRole.IT_ADMIN, UserRole.INVENTORY_MANAGER, UserRole.SITE_USER)
