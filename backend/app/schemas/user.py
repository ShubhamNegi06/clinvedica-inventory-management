"""Pydantic request/response schemas for User endpoints."""
import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, Field

from app.models.enums import UserRole


class UserCreate(BaseModel):
    """
    Used internally by user_service.create_user — the local `users` row
    is now created directly (no external identity provider to provision
    first). `id` is generated server-side (uuid4), never supplied by the
    caller.
    """

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
