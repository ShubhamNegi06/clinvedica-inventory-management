"""
Auth routes: register, login, refresh, logout, me, forgot-password,
reset-password. Replaces the earlier Supabase-delegated version entirely
— this app now owns the full credential lifecycle.

Refresh token handling: the raw refresh token is set as an httpOnly,
Secure, SameSite=Lax cookie (never returned in a JSON body, never
touchable by client-side JS) — this is what makes XSS-stolen access
tokens a much smaller blast radius than a stolen refresh token would be.
The access token IS returned in the JSON body, since the frontend needs
it in memory to attach as a Bearer header on every other request.
"""
from fastapi import APIRouter, Depends, Header, Request, Response
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.config import get_settings
from app.core.exceptions import UnauthorizedError, ValidationAppError
from app.core.security import hash_password, validate_password_strength
from app.db.session import get_db
from app.models.enums import UserRole
from app.models.password_reset_token import TokenPurpose
from app.models.user import User
from app.schemas.auth import (
    AccessTokenResponse,
    ForgotPasswordRequest,
    LoginRequest,
    MessageResponse,
    RegisterRequest,
    ResetPasswordRequest,
)
from app.schemas.user import UserRead
from app.services import auth_service, user_service
from app.services.email_service import build_invite_email, build_password_reset_email

router = APIRouter(prefix="/auth", tags=["auth"])
settings = get_settings()


def _set_refresh_cookie(response: Response, raw_refresh_token: str) -> None:
    response.set_cookie(
        key=settings.REFRESH_TOKEN_COOKIE_NAME,
        value=raw_refresh_token,
        httponly=True,
        secure=settings.APP_ENV != "development",  # allow http:// locally, require https in staging/prod
        samesite="lax",
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60,
        path="/api/v1/auth",  # only sent to auth endpoints, not every request
    )


def _clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(key=settings.REFRESH_TOKEN_COOKIE_NAME, path="/api/v1/auth")


@router.post("/login", response_model=AccessTokenResponse)
def login(payload: LoginRequest, response: Response, db: Session = Depends(get_db)):
    user = auth_service.authenticate_user(db, payload.email, payload.password)
    access_token, raw_refresh_token, _expires_at = auth_service.issue_token_pair(db, user)
    _set_refresh_cookie(response, raw_refresh_token)
    return AccessTokenResponse(
        access_token=access_token,
        expires_in_minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES,
        user=user,
    )


@router.post("/refresh", response_model=AccessTokenResponse)
def refresh(request: Request, response: Response, db: Session = Depends(get_db)):
    raw_refresh_token = request.cookies.get(settings.REFRESH_TOKEN_COOKIE_NAME)
    if not raw_refresh_token:
        raise UnauthorizedError("No active session. Please log in again.")

    access_token, new_raw_refresh_token, _expires_at, user = auth_service.refresh_token_pair(
        db, raw_refresh_token
    )
    _set_refresh_cookie(response, new_raw_refresh_token)
    return AccessTokenResponse(
        access_token=access_token,
        expires_in_minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES,
        user=user,
    )


@router.post("/logout", response_model=MessageResponse)
def logout(request: Request, response: Response, db: Session = Depends(get_db)):
    raw_refresh_token = request.cookies.get(settings.REFRESH_TOKEN_COOKIE_NAME)
    if raw_refresh_token:
        auth_service.revoke_refresh_token(db, raw_refresh_token)
    _clear_refresh_cookie(response)
    return MessageResponse(message="Logged out.")


@router.get("/me", response_model=UserRead)
def read_current_user(current_user: User = Depends(get_current_user)) -> User:
    """Returns the authenticated user's app-level profile (role, site, etc.)."""
    return current_user


def get_optional_current_user(
    authorization: str | None = None,
    db: Session = Depends(get_db),
) -> User | None:
    """
    Like get_current_user, but returns None instead of raising when no
    (or an invalid) token is presented. Used only by /auth/register,
    where whether authentication is REQUIRED depends on the
    ALLOW_PUBLIC_REGISTRATION setting rather than being a fixed rule.
    """
    from fastapi import Header

    from app.core.security import decode_token

    if authorization is None:
        return None
    if not authorization.lower().startswith("bearer "):
        return None
    token = authorization.split(" ", 1)[1].strip()
    try:
        payload = decode_token(token, expected_type="access")
        import uuid as _uuid

        user = db.get(User, _uuid.UUID(payload["sub"]))
        return user if (user and user.is_active) else None
    except Exception:  # noqa: BLE001 — any failure here just means "not authenticated", not an error to surface
        return None


@router.post("/register", response_model=UserRead, status_code=201)
def register(
    payload: RegisterRequest,
    db: Session = Depends(get_db),
    authorization: str | None = Header(default=None),
):
    """
    Registration is admin-gated by default (see
    Settings.ALLOW_PUBLIC_REGISTRATION) — this platform is internal/
    site-facing with admin-provisioned accounts by product design, not
    public sign-up. When ALLOW_PUBLIC_REGISTRATION is False (the
    default), this endpoint requires an existing IT Admin or Inventory
    Manager caller, making it a thin variant of POST /users for a
    self-chosen password instead of an emailed invite link.
    """
    current_user = get_optional_current_user(authorization, db)

    if not settings.ALLOW_PUBLIC_REGISTRATION:
        if current_user is None or current_user.role not in (UserRole.IT_ADMIN, UserRole.INVENTORY_MANAGER):
            from app.core.exceptions import PermissionDeniedError

            raise PermissionDeniedError("Registration is disabled. Contact your administrator for an account.")

    try:
        validate_password_strength(payload.password)
    except ValueError as exc:
        raise ValidationAppError(str(exc), field="password")

    from app.schemas.user import UserCreate

    creator = current_user or None
    if creator is None:
        # Public registration path: self-registered accounts default to
        # SITE_USER with no site — an admin must assign a site afterward.
        # There is no "creator" in this path, so we can't call
        # user_service.create_user (which requires an actor for the RBAC
        # check) — construct the row directly instead.
        import uuid as _uuid

        from app.models.user import User as UserModel

        user = UserModel(
            id=_uuid.uuid4(),
            email=payload.email.lower().strip(),
            full_name=payload.full_name,
            role=UserRole.SITE_USER,
            site_id=None,
            hashed_password=hash_password(payload.password),
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return user

    return user_service.create_user(
        db,
        UserCreate(email=payload.email, full_name=payload.full_name, role=UserRole.SITE_USER, site_id=None),
        created_by=creator,
        initial_password=payload.password,
    )


@router.post("/forgot-password", response_model=MessageResponse)
def forgot_password(payload: ForgotPasswordRequest, db: Session = Depends(get_db)):
    """
    Always returns the same generic message whether or not the email
    exists — this is what prevents user enumeration via this endpoint.
    The actual email (if the account exists) is sent asynchronously via
    Celery so this request never waits on SMTP.
    """
    from sqlalchemy import select

    user = db.execute(select(User).where(User.email == payload.email.lower().strip())).scalar_one_or_none()

    if user is not None and user.is_active:
        raw_token = auth_service.create_password_reset_token(db, user, TokenPurpose.RESET)
        reset_url = f"{settings.FRONTEND_URL.rstrip('/')}/set-password?token={raw_token}&purpose=reset"
        subject, html, text = build_password_reset_email(user.full_name, reset_url)

        from app.tasks.email_tasks import send_email_task

        send_email_task.delay(user.email, subject, html, text)

    return MessageResponse(message="If that email is registered, a password reset link has been sent.")


@router.post("/reset-password", response_model=MessageResponse)
def reset_password(payload: ResetPasswordRequest, db: Session = Depends(get_db)):
    auth_service.consume_password_reset_token(db, payload.token, payload.new_password)
    return MessageResponse(message="Password updated. Please log in with your new password.")
