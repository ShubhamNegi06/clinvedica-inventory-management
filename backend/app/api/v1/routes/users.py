"""
User management routes. Both IT_ADMIN and INVENTORY_MANAGER can create
users of any role per the product spec ("Create/manage Users (IT admin,
Inventory Manager and Site user)"). If you want to restrict Inventory
Managers from creating other IT Admins, tighten this with an additional
role check in create_user — left open for now per the spec as given.
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
      1. Create the Supabase Auth account (sends an invite email).
      2. Create the local `users` row with role/site_id.
    If step 2 fails, we delete the orphaned auth account rather than
    leaving an account that can log in but has no role in our system.
    """
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
    user = db.get(User, user_id)
    if user is None:
        raise NotFoundError("User not found.", field="user_id")
    return user_service.update_user(db, user, payload)
