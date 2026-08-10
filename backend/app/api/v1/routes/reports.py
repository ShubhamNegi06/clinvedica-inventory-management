"""
Report routes. Nested conceptually under a sample (every report belongs
to exactly one sample) but exposed as flat /reports endpoints since the
sample_id is always in the request body/query — this avoids deep path
nesting like /samples/{id}/reports/{id} while keeping the same
permission guarantees (scoped through the parent sample's site).
"""
import uuid

from fastapi import APIRouter, Depends, File, UploadFile
from sqlalchemy.orm import Session

from app.api.deps import get_accessible_site_ids, require_any_role
from app.core.exceptions import ValidationAppError
from app.db.session import get_db
from app.models.user import User
from app.schemas.report import ReportDownloadResponse, ReportRead
from app.services import report_service, sample_service
from app.core.config import get_settings

router = APIRouter(prefix="/reports", tags=["reports"])
settings = get_settings()

MAX_REPORT_SIZE_MB = 25
ALLOWED_CONTENT_TYPES = {"application/pdf"}


@router.get("/by-sample/{sample_id}", response_model=list[ReportRead])
def list_reports(
    sample_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_any_role),
):
    # get_sample already enforces the caller has access to this sample's site
    sample = sample_service.get_sample(db, current_user, sample_id)
    return report_service.list_reports_for_sample(db, sample)


@router.post("/by-sample/{sample_id}", response_model=ReportRead, status_code=201)
async def upload_report(
    sample_id: uuid.UUID,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_any_role),
):
    sample = sample_service.get_sample(db, current_user, sample_id)

    if file.content_type not in ALLOWED_CONTENT_TYPES:
        raise ValidationAppError(
            f"Unsupported file type '{file.content_type}'. Only PDF reports are accepted.", field="file"
        )

    contents = await file.read()
    size_mb = len(contents) / (1024 * 1024)
    if size_mb > MAX_REPORT_SIZE_MB:
        raise ValidationAppError(f"File exceeds the {MAX_REPORT_SIZE_MB}MB limit.", field="file")

    import io

    return report_service.upload_report(
        db,
        sample,
        current_user,
        file_obj=io.BytesIO(contents),
        filename=file.filename or "report.pdf",
        content_type=file.content_type,
        file_size_bytes=len(contents),
    )


@router.get("/{report_id}/download-url", response_model=ReportDownloadResponse)
def get_download_url(
    report_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_any_role),
):
    accessible = get_accessible_site_ids(current_user, db)
    _report, url = report_service.get_report_download_url(db, report_id, accessible)
    return ReportDownloadResponse(url=url, expires_in_seconds=settings.R2_SIGNED_URL_EXPIRY_SECONDS)


@router.delete("/{report_id}", status_code=204)
def delete_report(
    report_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_any_role),
):
    accessible = get_accessible_site_ids(current_user, db)
    report = report_service.get_report_for_access(db, report_id, accessible)
    report_service.delete_report(db, report)
