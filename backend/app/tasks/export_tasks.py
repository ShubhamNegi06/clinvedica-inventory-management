"""
Excel export Celery task.

Runs the (potentially slow, up to 10k rows) export entirely inside the
worker process — the FastAPI request handler that triggers this just
enqueues it and returns a task ID immediately (see
app/api/v1/routes/exports_async.py).

RBAC note: the task re-authenticates as the SAME user who requested the
export by re-fetching their User row with the user_id passed in — this
is what "Celery tasks respect the existing JWT authentication and RBAC
system" means in practice. sample_service.list_samples (called inside
export_samples_to_excel) applies the exact same get_accessible_site_ids
scoping it would during a normal synchronous request, so a Site User's
export can never contain another site's samples just because it ran in
a worker instead of a request handler.
"""
import logging
import uuid
from typing import List, Optional

from celery.exceptions import SoftTimeLimitExceeded

from app.core.celery_app import celery_app
from app.core.exceptions import AppError
from app.db.session import get_task_db_session
from app.models.user import User
from app.services import export_service, storage_service
from app.services.sample_service import FieldFilter

logger = logging.getLogger("specimen_inventory.tasks.export")


@celery_app.task(
    name="export_samples_task",
    bind=True,
    max_retries=2,
    retry_backoff=True,
    soft_time_limit=300,
    time_limit=360,
)
def export_samples_task(
    self,
    user_id: str,
    site_id: Optional[str] = None,
    field_filters: Optional[List[dict]] = None,
    search: Optional[str] = None,
) -> dict:
    """
    field_filters is passed as a list of {"field_key": ..., "value": ...}
    dicts (JSON-safe) rather than FieldFilter objects, since Celery task
    arguments must be JSON-serializable.
    """
    self.update_state(state="STARTED", meta={"stage": "loading_samples"})

    with get_task_db_session() as db:
        user = db.get(User, uuid.UUID(user_id))
        if user is None:
            raise AppError("Requesting user no longer exists.", field="user_id")

        filters = [FieldFilter(field_key=f["field_key"], value=f["value"]) for f in (field_filters or [])]

        try:
            buffer = export_service.export_samples_to_excel(
                db,
                user,
                site_id=uuid.UUID(site_id) if site_id else None,
                field_filters=filters,
                search=search,
            )
        except SoftTimeLimitExceeded:
            logger.error("Export task %s exceeded its time limit", self.request.id)
            raise

        self.update_state(state="STARTED", meta={"stage": "uploading_result"})

        filename = "specimen_inventory_export.xlsx"
        object_key = storage_service.build_export_object_key(user.id, filename)
        storage_service.upload_file(
            buffer,
            object_key,
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        download_url = storage_service.get_signed_download_url(object_key)

    return {"download_url": download_url, "file_name": filename}
