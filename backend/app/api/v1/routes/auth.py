"""
Auth routes. Login/logout/password-reset are handled entirely by
Supabase Auth on the frontend (supabase-js) — this backend never sees
credentials. The only thing we own here is resolving "who is this
already-authenticated user in OUR system", which the frontend calls right
after login to get role + site_id for routing to the correct dashboard.
"""
from fastapi import APIRouter, Depends

from app.api.deps import get_current_user
from app.models.user import User
from app.schemas.user import UserRead

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/me", response_model=UserRead)
def read_current_user(current_user: User = Depends(get_current_user)) -> User:
    """Returns the authenticated user's app-level profile (role, site, etc.)."""
    return current_user
