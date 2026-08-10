"""Pydantic request/response schemas for User endpoints."""
import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, Field

from app.models.enums import UserRole


class UserCreate(BaseModel):
    """
    Used by IT Admin / Inventory Manager to provision a new user.
    `id` is required because the Supabase Auth account must be created
    first (via Supabase Admin API, in app/services/auth_provisioning.py)
    and its issued UUID passed in here — we never generate our own.
    """

    id: uuid.UUID = Field(..., description="Supabase auth.users.id for the newly created account")
    email: EmailStr
    full_name: str = Field(..., min_length=1, max_length=255)
    role: UserRole
    site_id: Optional[uuid.UUID] = Field(
        default=None, description="Required when role=site_user; the site this user belongs to"
    )


class UserUpdate(BaseModel):
    full_name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    role: Optional[UserRole] = None
    site_id: Optional[uuid.UUID] = None
    is_active: Optional[bool] = None


class UserRead(BaseModel):
    id: uuid.UUID
    email: str
    full_name: str
    role: UserRole
    site_id: Optional[uuid.UUID]
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True
