"""
Business logic for User provisioning/listing/deletion.

Role restriction rule (applies throughout this file): an Inventory
Manager may create/edit/delete Inventory Manager and Site User accounts,
but NEVER IT Admin accounts — not creating one, not editing an existing
one's role/details, not deleting one. IT Admins are unrestricted. This is
enforced here (not just hidden in the UI) since the UI-only version was
exactly the kind of gap that let a Manager create an Admin account
before.
"""
from typing import List

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.exceptions import ConflictError, PermissionDeniedError, ValidationAppError
from app.models.enums import UserRole
from app.models.user import User
from app.schemas.user import UserCreate, UserUpdate


def list_users(db: Session) -> List[User]:
    """IT_ADMIN and INVENTORY_MANAGER both need full visibility to manage
    users; route-level require_manager_or_admin enforces who may call this."""
    return list(db.execute(select(User).order_by(User.created_at.desc())).scalars().all())


def _assert_can_manage_role(actor: User, target_role: UserRole) -> None:
    """Central check for the "Manager cannot touch IT Admin accounts" rule."""
    if actor.role == UserRole.INVENTORY_MANAGER and target_role == UserRole.IT_ADMIN:
        raise PermissionDeniedError("Inventory Managers cannot create or manage IT Admin accounts.")


def create_user(db: Session, payload: UserCreate, created_by: User) -> User:
    """
    Creates the local `users` row for an account that must already exist
    in Supabase Auth (see app/services/auth_provisioning.py — the caller
    is expected to have invoked that first and passed the resulting UUID
    as payload.id). This split keeps auth-provider concerns out of the
    core domain model.
    """
    _assert_can_manage_role(created_by, payload.role)

    if payload.role == UserRole.SITE_USER and payload.site_id is None:
        raise ValidationAppError("site_id is required when creating a Site User.", field="site_id")
    if payload.role != UserRole.SITE_USER and payload.site_id is not None:
        raise ValidationAppError(
            "site_id must be omitted for IT Admin / Inventory Manager accounts.", field="site_id"
        )

    user = User(
        id=payload.id,
        email=payload.email,
        full_name=payload.full_name,
        role=payload.role,
        site_id=payload.site_id,
        created_by=created_by.id,
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise ConflictError(f"A user with email '{payload.email}' already exists.", field="email")
    db.refresh(user)
    return user


def update_user(db: Session, actor: User, user: User, payload: UserUpdate) -> User:
    # A Manager can't touch an existing Admin account, and can't promote
    # anyone TO Admin either — check both the target's current role and
    # any role change being requested.
    _assert_can_manage_role(actor, user.role)
    if payload.role is not None:
        _assert_can_manage_role(actor, payload.role)

    updates = payload.model_dump(exclude_unset=True)

    new_role = updates.get("role", user.role)
    new_site_id = updates.get("site_id", user.site_id)
    if new_role == UserRole.SITE_USER and new_site_id is None:
        raise ValidationAppError("site_id is required for Site User accounts.", field="site_id")

    for field, value in updates.items():
        setattr(user, field, value)
    db.commit()
    db.refresh(user)
    return user


def delete_user(db: Session, actor: User, user: User) -> None:
    """
    Permanently deletes the local user row. The corresponding Supabase
    Auth account must be deleted separately by the caller (route) via
    auth_provisioning.delete_auth_user — kept as two explicit steps so a
    failure in either is visible rather than silently partial.
    """
    _assert_can_manage_role(actor, user.role)
    if actor.id == user.id:
        raise ValidationAppError("You cannot delete your own account.")
    db.delete(user)
    db.commit()
