"""
Bulk ingestion route — Excel upload -> enqueues a Celery task and returns
its task ID immediately, rather than parsing/inserting up to 5,000 rows
synchronously inside the request. Poll GET /tasks/{task_id} for status
and the per-row result breakdown once it completes.
"""
import uuid

from fastapi import APIRouter, Depends, File, UploadFile

from app.api.deps import require_any_role
from app.core.config import get_settings
from app.core.exceptions import ValidationAppError
from app.models.user import User
from app.schemas.task import TaskEnqueuedResponse

router = APIRouter(prefix="/samples/bulk-ingest", tags=["samples"])
settings = get_settings()

ALLOWED_TYPES = {
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/vnd.ms-excel",
}


@router.post("/{site_id}", response_model=TaskEnqueuedResponse, status_code=202)
async def bulk_ingest(
    site_id: uuid.UUID,
    file: UploadFile = File(...),
    current_user: User = Depends(require_any_role),
):
    if file.content_type not in ALLOWED_TYPES:
        raise ValidationAppError("Only .xlsx or .xls files are accepted for bulk ingestion.", field="file")

    contents = await file.read()
    size_mb = len(contents) / (1024 * 1024)
    if size_mb > settings.BULK_INGEST_MAX_FILE_MB:
        raise ValidationAppError(
            f"File exceeds the {settings.BULK_INGEST_MAX_FILE_MB}MB limit for bulk uploads.", field="file"
        )

    from app.tasks.bulk_ingest_tasks import bulk_ingest_samples_task

    task = bulk_ingest_samples_task.delay(str(current_user.id), str(site_id), contents.hex())
    return TaskEnqueuedResponse(task_id=task.id)
