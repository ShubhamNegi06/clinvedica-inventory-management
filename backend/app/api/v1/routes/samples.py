"""
Sample routes. Available to all three roles — `require_any_role` lets
everyone in, and permission scoping to the RIGHT samples happens inside
sample_service via get_accessible_site_ids, not here. This keeps the
route thin and the scoping logic in exactly one place.

NOTE on naming: the URL path parameter is called `sample_pk` (the
database row's UUID), deliberately distinct from the `sample_id` business
field (the template's "Sample ID" column, e.g. "GB-01FFPE1"). The URL
itself is unchanged (/samples/<uuid>) — this is just a Python-side rename
for clarity now that "sample_id" also means something else in this app.
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
from app.services.sample_service import FieldFilter

router = APIRouter(prefix="/samples", tags=["samples"])


def _parse_field_filters(raw_filters: Optional[List[str]]) -> List[FieldFilter]:
    """
    Parses "field_key:value" query strings into FieldFilter objects.
    Malformed entries (no colon) are ignored rather than erroring — a
    filter UI issue shouldn't 400 the whole list request.
    """
    filters: List[FieldFilter] = []
    for raw in raw_filters or []:
        if ":" not in raw:
            continue
        key, _, value = raw.partition(":")
        key, value = key.strip(), value.strip()
        if key and value:
            filters.append(FieldFilter(field_key=key, value=value))
    return filters


@router.get("", response_model=SampleListResponse)
def list_samples(
    site_id: Optional[uuid.UUID] = Query(default=None),
    field_filter: Optional[List[str]] = Query(
        default=None,
        description='Key:value filters against custom_fields, e.g. "tumor-percent:60" or "gender:Female". Repeatable.',
    ),
    search: Optional[str] = Query(default=None, description="Matches subject_id or sample_id"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_any_role),
):
    items, total = sample_service.list_samples(
        db,
        current_user,
        site_id=site_id,
        field_filters=_parse_field_filters(field_filter),
        search=search,
        page=page,
        page_size=page_size,
    )
    return SampleListResponse(items=items, total=total, page=page, page_size=page_size)


@router.get("/{sample_pk}", response_model=SampleRead)
def get_sample(
    sample_pk: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_any_role),
):
    return sample_service.get_sample(db, current_user, sample_pk)


@router.post("", response_model=SampleRead, status_code=201)
def create_sample(
    payload: SampleCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_any_role),
):
    return sample_service.create_sample(db, current_user, payload)


@router.patch("/{sample_pk}", response_model=SampleRead)
def update_sample(
    sample_pk: uuid.UUID,
    payload: SampleUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_any_role),
):
    return sample_service.update_sample(db, current_user, sample_pk, payload)


@router.delete("/{sample_pk}", status_code=204)
def delete_sample(
    sample_pk: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_any_role),
):
    """Soft-deletes the sample and purges its reports (see sample_service.soft_delete_sample)."""
    sample_service.soft_delete_sample(db, current_user, sample_pk)
