"""
Sample routes. Available to all three roles — `require_any_role` lets
everyone in, and permission scoping to the RIGHT samples happens inside
sample_service via get_accessible_site_ids, not here. This keeps the
route thin and the scoping logic in exactly one place.
"""
import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, Query

from sqlalchemy.orm import Session

from app.api.deps import require_any_role
from app.db.session import get_db
from app.models.user import User
from app.schemas.sample import SampleCreate, SampleListResponse, SampleRead, SampleUpdate
from app.services import sample_service

router = APIRouter(prefix="/samples", tags=["samples"])


@router.get("", response_model=SampleListResponse)
def list_samples(
    site_id: Optional[uuid.UUID] = Query(default=None),
    tags: Optional[List[str]] = Query(default=None, description="Filter: samples matching ANY of these tags"),
    search: Optional[str] = Query(default=None, description="Matches subject_id or sample_id"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_any_role),
):
    items, total = sample_service.list_samples(
        db, current_user, site_id=site_id, tags=tags, search=search, page=page, page_size=page_size
    )
    return SampleListResponse(items=items, total=total, page=page, page_size=page_size)


@router.get("/{sample_id}", response_model=SampleRead)
def get_sample(
    sample_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_any_role),
):
    return sample_service.get_sample(db, current_user, sample_id)


@router.post("", response_model=SampleRead, status_code=201)
def create_sample(
    payload: SampleCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_any_role),
):
    return sample_service.create_sample(db, current_user, payload)


@router.patch("/{sample_id}", response_model=SampleRead)
def update_sample(
    sample_id: uuid.UUID,
    payload: SampleUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_any_role),
):
    return sample_service.update_sample(db, current_user, sample_id, payload)


@router.delete("/{sample_id}", status_code=204)
def delete_sample(
    sample_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_any_role),
):
    """
    Soft-deletes the sample. NOTE: report/R2 cleanup for this sample is
    wired in Phase 2 (reports router) — this deliberately will NOT repeat
    the v1 orphaned-reports bug because that cleanup will be a required
    step inside this same service call once reports exist, not bolted on
    after the fact.
    """
    sample_service.soft_delete_sample(db, current_user, sample_id)
