"""Bulk ingestion route — Excel upload -> validated per-row sample creation."""
import uuid

from fastapi import APIRouter, Depends, File, UploadFile
from sqlalchemy.orm import Session

from app.api.deps import require_any_role
from app.core.config import get_settings
from app.core.exceptions import ValidationAppError
from app.db.session import get_db
from app.models.user import User
from app.services import bulk_ingest_service

router = APIRouter(prefix="/samples/bulk-ingest", tags=["samples"])
settings = get_settings()


@router.post("/{site_id}")
async def bulk_ingest(
    site_id: uuid.UUID,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_any_role),
):
    allowed_types = {
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "application/vnd.ms-excel",
    }
    if file.content_type not in allowed_types:
        raise ValidationAppError("Only .xlsx or .xls files are accepted for bulk ingestion.", field="file")

    contents = await file.read()
    size_mb = len(contents) / (1024 * 1024)
    if size_mb > settings.BULK_INGEST_MAX_FILE_MB:
        raise ValidationAppError(
            f"File exceeds the {settings.BULK_INGEST_MAX_FILE_MB}MB limit for bulk uploads.", field="file"
        )

    return bulk_ingest_service.parse_and_ingest(
        db, current_user, site_id, contents, max_rows=settings.BULK_INGEST_MAX_ROWS
    )
