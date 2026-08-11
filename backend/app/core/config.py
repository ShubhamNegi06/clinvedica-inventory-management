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

    # --- Database (Supabase Postgres) ---
    DATABASE_URL: str  # postgresql+psycopg://user:pass@host:port/dbname

    # --- Supabase Auth (ES256 JWT via JWKS) ---
    SUPABASE_URL: str  # e.g. https://zatytfclhrmupuaywxbb.supabase.co
    SUPABASE_ANON_KEY: str  # required as `apikey` header when hitting JWKS endpoint
    SUPABASE_SERVICE_ROLE_KEY: str  # server-side only — used to provision auth accounts via Admin API
    SUPABASE_JWT_AUDIENCE: str = "authenticated"

    @property
    def SUPABASE_JWKS_URL(self) -> str:
        return f"{self.SUPABASE_URL}/auth/v1/.well-known/jwks.json"

    # --- Cloudflare R2 (S3-compatible) ---
    R2_ACCOUNT_ID: str
    R2_ACCESS_KEY_ID: str
    R2_SECRET_ACCESS_KEY: str
    R2_BUCKET_NAME: str
    R2_SIGNED_URL_EXPIRY_SECONDS: int = 300  # short-lived, esp. for redacted reports

    @property
    def R2_ENDPOINT_URL(self) -> str:
        return f"https://{self.R2_ACCOUNT_ID}.r2.cloudflarestorage.com"

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
    # Used to build the redirect_to link for Supabase invite/recovery
    # emails, so "set your password" links land on OUR set-password page
    # instead of nowhere. This was the root cause of the invite-email
    # bug: without redirect_to, Supabase sends the user back to
    # SUPABASE_URL's default site (or nothing usable) instead of the app.
    FRONTEND_URL: str = "http://localhost:3000"

    # --- Bulk ingestion limits (guard rails, not arbitrary) ---
    BULK_INGEST_MAX_ROWS: int = 5000
    BULK_INGEST_MAX_FILE_MB: int = 20


@lru_cache
def get_settings() -> Settings:
    """Settings are cached — env is read once per process, not per request."""
    return Settings()
