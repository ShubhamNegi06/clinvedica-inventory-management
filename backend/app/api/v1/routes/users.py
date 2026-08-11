"""
User management routes.

Role rule enforced throughout (see app/services/user_service.py for the
central check): Inventory Managers may create/edit/delete Inventory
Manager and Site User accounts, but never IT Admin accounts. IT Admins
are unrestricted. This is checked server-side regardless of what the
frontend shows/hides.

Auth note: user creation no longer talks to an external identity
provider (no more Supabase Admin API round-trip). The local row is
created directly with a random, never-communicated placeholder password,
and an invite email (with a "set your password" link) is sent
asynchronously via Celery — the request returns as soon as the DB row
exists, without waiting on SMTP delivery.
"""
import uuid

from fastapi import APIRouter, Depends, Header
from pydantic import BaseModel, EmailStr

from sqlalchemy.orm import Session

from app.api.deps import require_manager_or_admin
from app.core.config import get_settings
from app.core.exceptions import NotFoundError
from app.core.security import generate_opaque_token
from app.db.session import get_db
from app.models.enums import UserRole
from app.models.password_reset_token import TokenPurpose
from app.models.user import User
from app.schemas.user import UserCreate, UserRead, UserUpdate
from app.services import auth_service, user_service
from app.services.email_service import build_invite_email, build_password_reset_email

router = APIRouter(prefix="/users", tags=["users"])
settings = get_settings()


class CreateUserRequest(BaseModel):
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
    Creates the local user row (with a random unusable placeholder
    password) then enqueues an invite email — the account only becomes
    usable once the recipient follows that link and sets a real password
    via POST /auth/reset-password.
    """
    placeholder_password = generate_opaque_token()

    user = user_service.create_user(
        db,
        UserCreate(email=payload.email, full_name=payload.full_name, role=payload.role, site_id=payload.site_id),
        created_by=current_user,
        initial_password=placeholder_password,
    )

    raw_token = auth_service.create_password_reset_token(db, user, TokenPurpose.INVITE)
    set_password_url = f"{settings.FRONTEND_URL.rstrip('/')}/set-password?token={raw_token}&purpose=invite"
    subject, html, text = build_invite_email(user.full_name, set_password_url)

    from app.tasks.email_tasks import send_email_task

    send_email_task.delay(user.email, subject, html, text)

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
    """Deletes the local user row. Any outstanding refresh/reset tokens
    for this user cascade-delete via FK — see user_service.delete_user."""
    user = _get_user_or_404(db, user_id)
    user_service.delete_user(db, current_user, user)


@router.post("/{user_id}/send-password-reset", status_code=200)
def send_password_reset(
    user_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_manager_or_admin),
):
    """Sends the user a 'reset your password' email asynchronously via Celery."""
    user = _get_user_or_404(db, user_id)
    if current_user.role == UserRole.INVENTORY_MANAGER and user.role == UserRole.IT_ADMIN:
        from app.core.exceptions import PermissionDeniedError

        raise PermissionDeniedError("Inventory Managers cannot manage IT Admin accounts.")

    raw_token = auth_service.create_password_reset_token(db, user, TokenPurpose.RESET)
    reset_url = f"{settings.FRONTEND_URL.rstrip('/')}/set-password?token={raw_token}&purpose=reset"
    subject, html, text = build_password_reset_email(user.full_name, reset_url)

    from app.tasks.email_tasks import send_email_task

    task = send_email_task.delay(user.email, subject, html, text)

    return {"message": f"Password reset email queued for {user.email}.", "task_id": task.id}


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

    temp_password = auth_service.set_temporary_password(db, user)
    return TemporaryPasswordResponse(temporary_password=temp_password)
