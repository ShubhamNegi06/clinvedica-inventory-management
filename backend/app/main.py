"""
Application entrypoint.

Every route in this app raises `AppError` subclasses for domain failures
(see app/core/exceptions.py). This single handler is what turns those into
a uniform JSON error shape for the frontend — no route handler should ever
need its own try/except-to-JSON boilerplate.
"""
import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.v1.routes import router as api_v1_router
from app.core.config import get_settings
from app.core.exceptions import AppError

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("specimen_inventory")

settings = get_settings()

app = FastAPI(
    title=settings.APP_NAME,
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS_LIST,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    """
    Uniform error response for every handled domain error:
        { "error_code": "...", "message": "...", "field": "..." }
    Unhandled/unexpected exceptions are logged with full context but NEVER
    leak internal details (stack traces, SQL, etc.) to the client.
    """
    payload = {"error_code": exc.error_code, "message": exc.message}
    if getattr(exc, "field", None):
        payload["field"] = exc.field
    if getattr(exc, "row_errors", None):
        payload["row_errors"] = exc.row_errors

    if exc.status_code >= 500:
        logger.error("Unhandled AppError on %s %s: %s", request.method, request.url.path, exc.message)

    return JSONResponse(status_code=exc.status_code, content=payload)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Last-resort catch-all — logs full detail server-side, returns a generic message to the client."""
    logger.exception("Unhandled exception on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={"error_code": "internal_error", "message": "An unexpected error occurred. Please try again."},
    )


app.include_router(api_v1_router, prefix=settings.API_V1_PREFIX)


@app.get("/health", tags=["system"])
def health_check() -> dict:
    """Lightweight liveness probe for deployment platforms (Railway/Render/etc.)."""
    return {"status": "ok", "app": settings.APP_NAME, "env": settings.APP_ENV}
