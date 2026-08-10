"""
Report business logic.

`purge_reports_for_sample` is the fix for the known v1 issue: sample
deletion was leaving orphaned rows in `reports` and orphaned objects in
R2, because report cleanup was a helper bolted on separately from the
delete path and (per the v1 diagnosis) may never have actually been
picked up by a running server. Here, cleanup is called directly inside
`sample_service.soft_delete_sample` in the same request/transaction —
there is no code path that deletes a sample without going through this
function first.
"""
import logging
import uuid
from typing import BinaryIO, List

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError
from app.models.report import Report
from app.models.sample import Sample
from app.models.user import User
from app.services import storage_service

logger = logging.getLogger("specimen_inventory.reports")


def list_reports_for_sample(db: Session, sample: Sample) -> List[Report]:
    stmt = select(Report).where(Report.sample_id == sample.id).order_by(Report.created_at.desc())
    return list(db.execute(stmt).scalars().all())


def upload_report(
    db: Session,
    sample: Sample,
    current_user: User,
    file_obj: BinaryIO,
    filename: str,
    content_type: str,
    file_size_bytes: int,
) -> Report:
    object_key = storage_service.build_object_key(sample.site_id, sample.id, filename)
    storage_service.upload_file(file_obj, object_key, content_type)

    report = Report(
        id=uuid.uuid4(),
        sample_id=sample.id,
        site_id=sample.site_id,
        file_key=object_key,
        file_name=filename,
        file_size_bytes=file_size_bytes,
        content_type=content_type,
        uploaded_by=current_user.id,
    )
    db.add(report)
    db.commit()
    db.refresh(report)
    return report


def get_report_for_access(db: Session, report_id: uuid.UUID, accessible_site_ids) -> Report:
    """Fetches a report and verifies the caller may access it, without minting a download URL."""
    report = db.get(Report, report_id)
    if report is None:
        raise NotFoundError("Report not found.", field="report_id")
    if accessible_site_ids is not None and report.site_id not in accessible_site_ids:
        from app.core.exceptions import PermissionDeniedError

        raise PermissionDeniedError("You do not have access to this report.")
    return report


def get_report_download_url(db: Session, report_id: uuid.UUID, accessible_site_ids) -> tuple[Report, str]:
    report = get_report_for_access(db, report_id, accessible_site_ids)
    url = storage_service.get_signed_download_url(report.file_key)
    return report, url


def delete_report(db: Session, report: Report) -> None:
    """Deletes a single report: R2 object first, then the DB row — if R2
    delete fails, we raise and do NOT delete the DB row, so the two never
    drift out of sync (no DB row pointing at a "deleted" object, and no
    orphaned object with no DB row)."""
    storage_service.delete_object(report.file_key)
    db.delete(report)
    db.commit()


def purge_reports_for_sample(db: Session, sample_id: uuid.UUID) -> None:
    """
    Deletes every report (R2 object + DB row) belonging to a sample.
    Called synchronously as part of sample deletion — see
    sample_service.soft_delete_sample. Each object's failure is logged
    individually so a single bad delete doesn't silently swallow the rest.
    """
    stmt = select(Report).where(Report.sample_id == sample_id)
    reports = list(db.execute(stmt).scalars().all())

    for report in reports:
        try:
            storage_service.delete_object(report.file_key)
        except Exception:
            # Logged inside storage_service already with the
            # `R2 object delete failed` signal line. We still remove the
            # DB row below — an orphaned R2 object is a much smaller
            # problem (cleanable by a periodic reconciliation job) than a
            # DB row that permanently blocks the sample from being
            # cleanly deleted.
            logger.warning("Continuing purge despite R2 delete failure for report_id=%s", report.id)
        db.delete(report)

    db.commit()
