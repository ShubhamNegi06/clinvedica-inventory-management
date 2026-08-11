"""
Centralized application configuration.

All environment-dependent values are declared here and nowhere else in the
codebase. This keeps secrets out of source, makes local/staging/prod parity
easy to reason about, and gives us a single place to validate required
config at startup (fail fast instead of failing deep inside a request).
"""
from functools import lru_cache
from typing import List

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- App ---
    APP_NAME: str = "Clinvedica Specimen Inventory API"
    APP_ENV: str = Field(default="development")  # development | staging | production
    API_V1_PREFIX: str = "/api/v1"
    DEBUG: bool = False

    # --- Database (Supabase Postgres — used purely as a Postgres host now,
    #     Supabase Auth is no longer involved anywhere in this app) ---
    DATABASE_URL: str  # postgresql+psycopg://user:pass@host:port/dbname

    # --- JWT auth (custom, replaces Supabase Auth) ---
    # JWT_SECRET_KEY signs BOTH access and refresh tokens (HS256,
    # symmetric) — this app now issues and verifies its own tokens, so
    # there's no more JWKS/asymmetric-key roundtrip to an external
    # identity provider. Generate with: openssl rand -hex 32
    JWT_SECRET_KEY: str
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30

    # Name of the httpOnly cookie the refresh token is stored in.
    REFRESH_TOKEN_COOKIE_NAME: str = "refresh_token"

    # --- Password reset / invite tokens ---
    PASSWORD_RESET_TOKEN_EXPIRE_MINUTES: int = 30
    INVITE_TOKEN_EXPIRE_HOURS: int = 72

    # Self-service registration is OFF by default — this platform is
    # internal/site-facing with admin-provisioned accounts by design (see
    # product spec: IT Admin / Inventory Manager create every user).
    # Flip to true only if you actually want public sign-up.
    ALLOW_PUBLIC_REGISTRATION: bool = False

    # --- SMTP (replaces Supabase's built-in email delivery) ---
    SMTP_HOST: str = "localhost"
    SMTP_PORT: int = 587
    SMTP_USERNAME: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM_EMAIL: str = "no-reply@clinvedica.com"
    SMTP_FROM_NAME: str = "Clinvedica Specimen Inventory"
    SMTP_USE_TLS: bool = True

    # --- Cloudflare R2 (S3-compatible) — unrelated to auth, unchanged ---
    R2_ACCOUNT_ID: str
    R2_ACCESS_KEY_ID: str
    R2_SECRET_ACCESS_KEY: str
    R2_BUCKET_NAME: str
    R2_SIGNED_URL_EXPIRY_SECONDS: int = 300  # short-lived, esp. for redacted reports

    @property
    def R2_ENDPOINT_URL(self) -> str:
        return f"https://{self.R2_ACCOUNT_ID}.r2.cloudflarestorage.com"

    # --- Redis / Celery ---
    REDIS_URL: str = "redis://localhost:6379/0"
    # Broker/backend default to REDIS_URL but can be pointed at separate
    # Redis instances/DBs in production if desired.
    CELERY_BROKER_URL: str = ""
    CELERY_RESULT_BACKEND: str = ""

    @property
    def CELERY_BROKER_URL_RESOLVED(self) -> str:
        return self.CELERY_BROKER_URL or self.REDIS_URL

    @property
    def CELERY_RESULT_BACKEND_RESOLVED(self) -> str:
        return self.CELERY_RESULT_BACKEND or self.REDIS_URL

    # --- CORS ---
    # Stored as a raw comma-separated string (not List[str]) because
    # pydantic-settings attempts JSON-decoding of list-typed env vars
    # before any validator runs, which breaks on a plain comma-separated
    # value like "http://a.com,http://b.com". Splitting is done in the
    # CORS_ORIGINS_LIST property instead.
    CORS_ORIGINS: str = "http://localhost:3000"

    @property
    def CORS_ORIGINS_LIST(self) -> List[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]

    # --- Frontend base URL ---
    # Used to build invite/password-reset email links (?token=...&purpose=...)
    # so they land on the frontend's /set-password page.
    FRONTEND_URL: str = "http://localhost:3000"

    # --- Bulk ingestion limits (guard rails, not arbitrary) ---
    BULK_INGEST_MAX_ROWS: int = 5000
    BULK_INGEST_MAX_FILE_MB: int = 20


@lru_cache
def get_settings() -> Settings:
    """Settings are cached — env is read once per process, not per request."""
    return Settings()
