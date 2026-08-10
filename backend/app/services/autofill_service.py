"""
Subject-ID autofill.

Two endpoints power this feature on the frontend:
  1. suggestions(q) — type-ahead list of matching subject_ids as the
     user types, scoped to sites they can access.
  2. autofill_for_subject(subject_id) — once a match is picked/typed
     fully, returns the most recent sample's custom_fields so the form
     can pre-populate fields flagged `is_autofill=True` on
     FieldDefinition.
"""
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_accessible_site_ids
from app.models.field_definition import FieldDefinition
from app.models.sample import Sample
from app.models.user import User


def suggest_subject_ids(db: Session, current_user: User, query: str, limit: int = 10) -> List[str]:
    accessible = get_accessible_site_ids(current_user, db)
    stmt = (
        select(Sample.subject_id)
        .where(Sample.is_deleted.is_(False), Sample.subject_id.ilike(f"%{query}%"))
        .distinct()
        .limit(limit)
    )
    if accessible is not None:
        stmt = stmt.where(Sample.site_id.in_(accessible))
    return [row[0] for row in db.execute(stmt).all()]


def autofill_for_subject(db: Session, current_user: User, subject_id: str) -> Optional[Dict[str, Any]]:
    """
    Returns only the fields marked is_autofill=True on FieldDefinition,
    pulled from the most recently created sample with a matching
    subject_id. Returns None if no prior sample exists for this subject
    (i.e. this is a genuinely new subject — nothing to prefill).
    """
    accessible = get_accessible_site_ids(current_user, db)
    stmt = (
        select(Sample)
        .where(Sample.is_deleted.is_(False), Sample.subject_id == subject_id)
        .order_by(Sample.created_at.desc())
        .limit(1)
    )
    if accessible is not None:
        stmt = stmt.where(Sample.site_id.in_(accessible))

    latest = db.execute(stmt).scalar_one_or_none()
    if latest is None:
        return None

    autofill_keys = {
        fd.field_key
        for fd in db.execute(
            select(FieldDefinition).where(FieldDefinition.is_autofill.is_(True), FieldDefinition.is_active.is_(True))
        ).scalars()
    }

    return {k: v for k, v in latest.custom_fields.items() if k in autofill_keys}
