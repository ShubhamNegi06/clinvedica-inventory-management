"""
Excel export route — enqueues a Celery task and returns its task ID
immediately rather than streaming the (potentially 10k-row) workbook
synchronously. Poll GET /tasks/{task_id}; on SUCCESS the result contains
a short-lived signed R2 download URL.
"""
from typing import List, Optional
import uuid

from fastapi import APIRouter, Depends, Query

from app.api.deps import require_any_role
from app.api.v1.routes.samples import _parse_field_filters
from app.models.user import User
from app.schemas.task import TaskEnqueuedResponse

router = APIRouter(prefix="/samples/export", tags=["samples"])


@router.get("", response_model=TaskEnqueuedResponse, status_code=202)
def export_samples(
    site_id: Optional[uuid.UUID] = Query(default=None),
    field_filter: Optional[List[str]] = Query(default=None),
    search: Optional[str] = Query(default=None),
    current_user: User = Depends(require_any_role),
):
    filters = _parse_field_filters(field_filter)

    from app.tasks.export_tasks import export_samples_task

    task = export_samples_task.delay(
        str(current_user.id),
        str(site_id) if site_id else None,
        [{"field_key": f.field_key, "value": f.value} for f in filters],
        search,
    )
    return TaskEnqueuedResponse(task_id=task.id)
