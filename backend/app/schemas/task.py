"""Pydantic schema for the generic Celery task-status endpoint."""
from typing import Any, Optional

from pydantic import BaseModel


class TaskStatusResponse(BaseModel):
    """
    `status` mirrors Celery's own task states directly: PENDING, STARTED,
    RETRY, SUCCESS, FAILURE. The frontend polls until status is SUCCESS
    or FAILURE.
    """

    task_id: str
    status: str
    progress: Optional[dict] = None
    result: Optional[Any] = None
    error: Optional[str] = None


class TaskEnqueuedResponse(BaseModel):
    """Returned immediately by every "start a background task" endpoint."""

    task_id: str
    status: str = "PENDING"
