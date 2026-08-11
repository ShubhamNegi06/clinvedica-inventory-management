"""
Multi-file report upload Celery task.

Moves the R2 upload(s) for a batch of report PDFs off the request
thread. Each file is uploaded independently (same per-file error
isolation the synchronous version had) so one bad/oversized file in a
batch of ten doesn't fail the other nine.
"""
import io
import logging
import uuid
from typing import List

from app.core.celery_app import celery_app
from app.core.exceptions import AppError, NotFoundError
from app.db.session import get_task_db_session
from app.models.sample import Sample
from app.models.user import User
from app.services import report_service

logger = logging.getLogger("specimen_inventory.tasks.reports")

MAX_REPORT_SIZE_MB = 25
ALLOWED_CONTENT_TYPES = {"application/pdf"}


@celery_app.task(
    name="upload_reports_task",
    bind=True,
    max_retries=2,
    retry_backoff=True,
    soft_time_limit=300,
    time_limit=360,
)
def upload_reports_task(self, user_id: str, sample_pk: str, files: List[dict]) -> dict:
    """
    `files` is a list of {"file_name": str, "content_type": str,
    "content_hex": str} dicts — hex-encoded bytes, since Celery task args
    must be JSON-serializable (see bulk_ingest_tasks.py for the same
    pattern).
    """
    self.update_state(state="STARTED", meta={"stage": "uploading", "total": len(files)})

    with get_task_db_session() as db:
        user = db.get(User, uuid.UUID(user_id))
        if user is None:
            raise AppError("Requesting user no longer exists.", field="user_id")

        sample = db.get(Sample, uuid.UUID(sample_pk))
        if sample is None or sample.is_deleted:
            raise NotFoundError("Sample not found.", field="sample_pk")

        # Same RBAC guarantee as export/bulk-ingest tasks: re-derive
        # access from the submitting user's actual role/site, not from
        # whatever context the worker happens to run in.
        from app.api.deps import get_accessible_site_ids

        accessible = get_accessible_site_ids(user, db)
        if accessible is not None and sample.site_id not in accessible:
            raise AppError("You do not have access to this sample's site.", field="sample_pk")

        uploaded = []
        errors = []

        for f in files:
            file_name = f.get("file_name") or "report.pdf"
            content_type = f.get("content_type")
            try:
                if content_type not in ALLOWED_CONTENT_TYPES:
                    raise ValueError(f"Unsupported file type '{content_type}'. Only PDF reports are accepted.")

                content_bytes = bytes.fromhex(f["content_hex"])
                size_mb = len(content_bytes) / (1024 * 1024)
                if size_mb > MAX_REPORT_SIZE_MB:
                    raise ValueError(f"File exceeds the {MAX_REPORT_SIZE_MB}MB limit.")

                report = report_service.upload_report(
                    db,
                    sample,
                    user,
                    file_obj=io.BytesIO(content_bytes),
                    filename=file_name,
                    content_type=content_type,
                    file_size_bytes=len(content_bytes),
                )
                uploaded.append({"id": str(report.id), "file_name": report.file_name})
            except Exception as exc:  # noqa: BLE001 — one bad file must not fail the whole batch
                logger.warning("Report upload failed for %s: %s", file_name, exc)
                errors.append({"file_name": file_name, "error": str(exc)})

    return {"uploaded": uploaded, "errors": errors}
