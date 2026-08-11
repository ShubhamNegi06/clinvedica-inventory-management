"""
User management routes.

Role rule enforced throughout (see app/services/user_service.py for the
central check): Inventory Managers may create/edit/delete Inventory
Manager and Site User accounts, but never IT Admin accounts. IT Admins
are unrestricted. This is checked server-side regardless of what the
frontend shows/hides.
"""
import uuid

from fastapi import APIRouter, Depends
from pydantic import BaseModel, EmailStr

from sqlalchemy.orm import Session

from app.api.deps import require_manager_or_admin
from app.core.exceptions import NotFoundError
from app.db.session import get_db
from app.models.enums import UserRole
from app.models.user import User
from app.schemas.user import UserCreate, UserRead, UserUpdate
from app.services import auth_provisioning, user_service

router = APIRouter(prefix="/users", tags=["users"])


class CreateUserRequest(BaseModel):
    """
    What the frontend actually submits: no Supabase UUID yet, since the
    Auth account doesn't exist until we provision it server-side. The
    route below handles the full provision -> create-local-row flow.
    """

    email: EmailStr
    full_name: str
    role: UserRole
    site_id: uuid.UUID | None = None


class TemporaryPasswordResponse(BaseModel):
    temporary_password: str


def _get_user_or_404(db: Session, user_id: uuid.UUID) -> User:
    user = db.get(User, user_id)
    if user is None:
        raise NotFoundError("User not found.", field="user_id")
    return user


@router.get("", response_model=list[UserRead])
def list_users(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_manager_or_admin),
):
    return user_service.list_users(db)


@router.post("", response_model=UserRead, status_code=201)
def create_user(
    payload: CreateUserRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_manager_or_admin),
):
    """
    Two-step provisioning with compensating rollback:
      1. Create the Supabase Auth account (sends an invite email with a
         redirect_to our /set-password page).
      2. Create the local `users` row with role/site_id — this is also
         where the "Manager cannot create IT Admin" rule is enforced
         (see user_service._assert_can_manage_role), BEFORE any Supabase
         account would be created, so we never provision an auth account
         for a request that was going to be rejected anyway.
    If step 2 fails after step 1 succeeds for any other reason, we delete
    the orphaned auth account rather than leaving an account that can log
    in but has no role in our system.
    """
    # Fail fast on the role rule before touching Supabase Auth at all.
    if current_user.role == UserRole.INVENTORY_MANAGER and payload.role == UserRole.IT_ADMIN:
        from app.core.exceptions import PermissionDeniedError

        raise PermissionDeniedError("Inventory Managers cannot create IT Admin accounts.")

    supabase_user_id = auth_provisioning.provision_auth_user(payload.email, payload.full_name)

    try:
        user = user_service.create_user(
            db,
            UserCreate(
                id=uuid.UUID(supabase_user_id),
                email=payload.email,
                full_name=payload.full_name,
                role=payload.role,
                site_id=payload.site_id,
            ),
            created_by=current_user,
        )
    except Exception:
        auth_provisioning.delete_auth_user(supabase_user_id)
        raise

    return user


@router.patch("/{user_id}", response_model=UserRead)
def update_user(
    user_id: uuid.UUID,
    payload: UserUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_manager_or_admin),
):
    user = _get_user_or_404(db, user_id)
    return user_service.update_user(db, current_user, user, payload)


@router.delete("/{user_id}", status_code=204)
def delete_user(
    user_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_manager_or_admin),
):
    """
    Deletes the user in both systems: local row first (so the role-check
    and self-delete guard in user_service run before we touch Supabase),
    then the Supabase Auth account. If the Supabase delete fails, the
    local row is already gone — this is logged via StorageError rather
    than silently swallowed, so an orphaned auth account is visible and
    fixable rather than invisible.
    """
    user = _get_user_or_404(db, user_id)
    supabase_user_id = str(user.id)
    user_service.delete_user(db, current_user, user)
    auth_provisioning.delete_auth_user(supabase_user_id)


@router.post("/{user_id}/send-password-reset", status_code=200)
def send_password_reset(
    user_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_manager_or_admin),
):
    """Sends the user a 'reset your password' email (same redirect flow as the invite)."""
    user = _get_user_or_404(db, user_id)
    if current_user.role == UserRole.INVENTORY_MANAGER and user.role == UserRole.IT_ADMIN:
        from app.core.exceptions import PermissionDeniedError

        raise PermissionDeniedError("Inventory Managers cannot manage IT Admin accounts.")
    auth_provisioning.send_password_reset_email(user.email)
    return {"message": f"Password reset email sent to {user.email}."}


@router.post("/{user_id}/set-temporary-password", response_model=TemporaryPasswordResponse)
def set_temporary_password(
    user_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_manager_or_admin),
):
    """Immediately sets a random temporary password and returns it ONCE for the admin to share out-of-band."""
    user = _get_user_or_404(db, user_id)
    if current_user.role == UserRole.INVENTORY_MANAGER and user.role == UserRole.IT_ADMIN:
        from app.core.exceptions import PermissionDeniedError

        raise PermissionDeniedError("Inventory Managers cannot manage IT Admin accounts.")
    temp_password = auth_provisioning.set_temporary_password(str(user.id))
    return TemporaryPasswordResponse(temporary_password=temp_password)
