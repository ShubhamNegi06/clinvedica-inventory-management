"""
Bulk sample ingestion Celery task — wraps bulk_ingest_service.parse_and_ingest
so a large (up to BULK_INGEST_MAX_ROWS) Excel upload doesn't tie up a
request worker for however long the per-row validation/insert takes.

Same RBAC note as export_tasks.py: the task re-fetches the submitting
user's own User row and calls assert_site_access exactly as the
synchronous path did, so a Site User still can't bulk-ingest into a site
they don't own just because the work happens in a worker process.
"""
import logging
import uuid

from app.core.celery_app import celery_app
from app.core.exceptions import AppError, BulkIngestError
from app.db.session import get_task_db_session
from app.models.user import User
from app.services import bulk_ingest_service
from app.core.config import get_settings

logger = logging.getLogger("specimen_inventory.tasks.bulk_ingest")
settings = get_settings()


@celery_app.task(
    name="bulk_ingest_samples_task",
    bind=True,
    max_retries=0,  # a partially-applied bulk ingest should not be blindly retried — see note below
    soft_time_limit=480,
    time_limit=540,
)
def bulk_ingest_samples_task(self, user_id: str, site_id: str, file_bytes_hex: str) -> dict:
    """
    `file_bytes_hex` is the uploaded file's bytes hex-encoded, since raw
    bytes aren't JSON-serializable as a Celery task argument. Retries are
    disabled by default (max_retries=0): parse_and_ingest already commits
    successfully-parsed rows as it goes (per-row savepoints), so blindly
    retrying the whole task on failure could re-attempt rows that already
    succeeded. If retry behavior is wanted here, it should be built as
    upsert-by-sample_id semantics first — left as a known limitation
    rather than silently doing the unsafe thing.
    """
    self.update_state(state="STARTED", meta={"stage": "parsing_file"})

    with get_task_db_session() as db:
        user = db.get(User, uuid.UUID(user_id))
        if user is None:
            raise AppError("Requesting user no longer exists.", field="user_id")

        file_bytes = bytes.fromhex(file_bytes_hex)

        try:
            result = bulk_ingest_service.parse_and_ingest(
                db, user, uuid.UUID(site_id), file_bytes, max_rows=settings.BULK_INGEST_MAX_ROWS
            )
        except BulkIngestError as exc:
            # Surface the structured row-error breakdown in the task
            # result rather than losing it to a generic FAILURE state
            # with just a string message.
            return {
                "success": False,
                "error_code": exc.error_code,
                "message": exc.message,
                "row_errors": exc.row_errors,
            }
        except AppError as exc:
            return {"success": False, "error_code": exc.error_code, "message": exc.message}

    return {"success": True, **result}
