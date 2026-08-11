"""Pydantic request/response schemas for auth endpoints."""
from pydantic import BaseModel, EmailStr, Field

from app.schemas.user import UserRead


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=1)


class AccessTokenResponse(BaseModel):
    """
    Returned by /auth/login and /auth/refresh. The refresh token itself
    is NEVER included in this body — it's set as an httpOnly cookie by
    the route, so client-side JS never has direct access to it (mitigates
    XSS token theft). The access token IS returned here because the
    frontend needs it in memory to attach as a Bearer header.
    """

    access_token: str
    token_type: str = "bearer"
    expires_in_minutes: int
    user: UserRead


class RegisterRequest(BaseModel):
    email: EmailStr
    full_name: str = Field(..., min_length=1, max_length=255)
    password: str = Field(..., min_length=8)


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str = Field(..., min_length=8)


class MessageResponse(BaseModel):
    message: str
