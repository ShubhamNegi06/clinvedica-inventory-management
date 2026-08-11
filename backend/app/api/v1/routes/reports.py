"""
Report routes. Nested conceptually under a sample (every report belongs
to exactly one sample) but exposed as flat /reports endpoints since the
sample's row id is always in the request path — this avoids deep path
nesting like /samples/{id}/reports/{id} while keeping the same
permission guarantees (scoped through the parent sample's site).

NOTE on naming: `sample_pk` is the sample row's UUID (Sample.id), kept
distinct from `sample_id` the business field, same convention as in
app/api/v1/routes/samples.py.

Upload is the one Celery-backed endpoint here — list/download-url/delete
stay synchronous since they're fast single-row operations that don't
benefit from being backgrounded, and instant feedback matters more for
them than for a multi-file upload.
"""
import uuid
from typing import List

from fastapi import APIRouter, Depends, File, UploadFile
from sqlalchemy.orm import Session

from app.api.deps import get_accessible_site_ids, require_any_role
from app.core.config import get_settings
from app.db.session import get_db
from app.models.user import User
from app.schemas.report import ReportDownloadResponse, ReportRead
from app.schemas.task import TaskEnqueuedResponse
from app.services import report_service, sample_service

router = APIRouter(prefix="/reports", tags=["reports"])
settings = get_settings()

MAX_REPORT_SIZE_MB = 25
ALLOWED_CONTENT_TYPES = {"application/pdf"}


@router.get("/by-sample/{sample_pk}", response_model=list[ReportRead])
def list_reports(
    sample_pk: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_any_role),
):
    # get_sample already enforces the caller has access to this sample's site
    sample = sample_service.get_sample(db, current_user, sample_pk)
    return report_service.list_reports_for_sample(db, sample)


@router.post("/by-sample/{sample_pk}", response_model=TaskEnqueuedResponse, status_code=202)
async def upload_reports(
    sample_pk: uuid.UUID,
    files: List[UploadFile] = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_any_role),
):
    """
    Accepts one or more PDF files (multipart field name "files",
    repeated) and enqueues a single Celery task that uploads all of them
    to R2 — the fix for "can only upload one report at a time" plus
    moving the R2 I/O off the request thread. Poll GET /tasks/{task_id};
    the result contains per-file uploaded/errors breakdown, same shape
    the old synchronous response had.
    """
    # get_sample enforces access before we even read file bytes, so a
    # caller without access to this sample gets a 403/404 immediately
    # rather than after uploading potentially large files for nothing.
    sample_service.get_sample(db, current_user, sample_pk)

    file_payloads = []
    for file in files:
        contents = await file.read()
        file_payloads.append(
            {
                "file_name": file.filename or "report.pdf",
                "content_type": file.content_type,
                "content_hex": contents.hex(),
            }
        )

    from app.tasks.report_tasks import upload_reports_task

    task = upload_reports_task.delay(str(current_user.id), str(sample_pk), file_payloads)
    return TaskEnqueuedResponse(task_id=task.id)


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
