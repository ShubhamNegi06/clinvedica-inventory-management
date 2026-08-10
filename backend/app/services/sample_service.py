"""
Business logic for Sample CRUD. All list/get operations are scoped by
`get_accessible_site_ids` so a Site User can never see another site's
samples even if they guess an ID — the scoping happens at the query
level, not just at the route/permission-check level, which is the safer
pattern (defense in depth).
"""
import uuid
from typing import List, Optional, Tuple

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import get_accessible_site_ids
from app.core.exceptions import ConflictError, NotFoundError
from app.models.sample import Sample
from app.models.user import User
from app.schemas.sample import SampleCreate, SampleUpdate


def _base_query(current_user: User, db: Session):
    accessible = get_accessible_site_ids(current_user, db)
    stmt = select(Sample).where(Sample.is_deleted.is_(False))
    if accessible is not None:
        stmt = stmt.where(Sample.site_id.in_(accessible))
    return stmt


def list_samples(
    db: Session,
    current_user: User,
    *,
    site_id: Optional[uuid.UUID] = None,
    tags: Optional[List[str]] = None,
    search: Optional[str] = None,
    page: int = 1,
    page_size: int = 25,
) -> Tuple[List[Sample], int]:
    """
    Filters:
      - site_id: narrow to one site (still permission-checked)
      - tags: samples containing ANY of the given tags (tag filtering feature)
      - search: matches subject_id or sample_id, case-insensitive
    """
    stmt = _base_query(current_user, db)

    if site_id is not None:
        stmt = stmt.where(Sample.site_id == site_id)
    if tags:
        stmt = stmt.where(Sample.tags.overlap(tags))
    if search:
        like = f"%{search.strip()}%"
        stmt = stmt.where(
            (Sample.subject_id.ilike(like)) | (Sample.sample_id.ilike(like))
        )

    total = db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()

    stmt = stmt.order_by(Sample.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    items = list(db.execute(stmt).scalars().all())
    return items, total


def get_sample(db: Session, current_user: User, sample_id: uuid.UUID) -> Sample:
    stmt = _base_query(current_user, db).where(Sample.id == sample_id)
    sample = db.execute(stmt).scalar_one_or_none()
    if sample is None:
        raise NotFoundError("Sample not found.", field="sample_id")
    return sample


def create_sample(db: Session, current_user: User, payload: SampleCreate) -> Sample:
    from app.api.deps import assert_site_access

    assert_site_access(payload.site_id, current_user, db)

    sample = Sample(
        id=uuid.uuid4(),
        site_id=payload.site_id,
        subject_id=payload.subject_id,
        sample_id=payload.sample_id,
        sample_type=payload.sample_type,
        tags=payload.tags,
        custom_fields=payload.custom_fields,
        created_by=current_user.id,
        updated_by=current_user.id,
    )
    db.add(sample)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        # Mirrors the v1 lesson: use the DB constraint name as the
        # reliable signal, not a fragile string match on the raw message,
        # and never leak the raw Postgres error to the client.
        constraint = getattr(getattr(exc.orig, "diag", None), "constraint_name", None)
        if constraint == "uq_sample_site_code":
            raise ConflictError(
                f"Sample code '{payload.sample_id}' already exists at this site.",
                field="sample_id",
            )
        raise
    db.refresh(sample)
    return sample


def update_sample(db: Session, current_user: User, sample_id: uuid.UUID, payload: SampleUpdate) -> Sample:
    sample = get_sample(db, current_user, sample_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(sample, field, value)
    sample.updated_by = current_user.id
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise ConflictError(
            f"Sample code '{payload.sample_id}' already exists at this site.", field="sample_id"
        )
    db.refresh(sample)
    return sample


def soft_delete_sample(db: Session, current_user: User, sample_id: uuid.UUID) -> None:
    """
    Soft-deletes the sample AND purges its reports (R2 objects + DB rows)
    in the same call. This directly fixes the v1 bug where report cleanup
    was a separate helper that silently never ran — here it is not
    optional and not a separate step the caller could forget.
    """
    from app.services import report_service

    sample = get_sample(db, current_user, sample_id)
    report_service.purge_reports_for_sample(db, sample.id)

    sample.is_deleted = True
    sample.updated_by = current_user.id
    db.commit()
