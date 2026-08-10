"""
Application-level exception hierarchy.

Why this exists: raw exceptions (psycopg IntegrityError, KeyError, etc.)
leak internal details to clients and are inconsistent to handle in routes.
Every domain error in this app should raise one of these, and a single
FastAPI exception handler (see app/main.py) converts them into a uniform
JSON error shape:

    { "error_code": "...", "message": "...", "field": "..." }

This mirrors the pattern already proven out in the v1 backend for
sample_id conflicts — generalized here for the whole app.
"""
from typing import Optional


class AppError(Exception):
    """Base class for all handled application errors."""

    status_code: int = 500
    error_code: str = "internal_error"

    def __init__(self, message: str, field: Optional[str] = None):
        self.message = message
        self.field = field
        super().__init__(message)


class NotFoundError(AppError):
    status_code = 404
    error_code = "not_found"


class PermissionDeniedError(AppError):
    status_code = 403
    error_code = "permission_denied"


class UnauthorizedError(AppError):
    status_code = 401
    error_code = "unauthorized"


class ConflictError(AppError):
    """Uniqueness violations, duplicate sample codes, etc."""

    status_code = 409
    error_code = "conflict"


class ValidationAppError(AppError):
    """Domain validation failures that don't fit Pydantic's request-shape validation."""

    status_code = 422
    error_code = "validation_error"


class BulkIngestError(AppError):
    """
    Raised for bulk-ingestion failures. `row_errors` carries a per-row
    breakdown so the frontend can show the user exactly which rows failed
    and why, instead of aborting the whole file on one bad row.
    """

    status_code = 422
    error_code = "bulk_ingest_error"

    def __init__(self, message: str, row_errors: Optional[list] = None):
        self.row_errors = row_errors or []
        super().__init__(message)


class StorageError(AppError):
    """R2 upload/download/delete failures."""

    status_code = 502
    error_code = "storage_error"
