"""Subject ID autofill routes — type-ahead suggestions + prefill lookup."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import require_any_role
from app.db.session import get_db
from app.models.user import User
from app.services import autofill_service

router = APIRouter(prefix="/subjects", tags=["subjects"])


@router.get("/suggestions")
def get_suggestions(
    q: str = Query(..., min_length=1),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_any_role),
):
    return {"suggestions": autofill_service.suggest_subject_ids(db, current_user, q)}


@router.get("/{subject_id}/autofill")
def get_autofill(
    subject_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_any_role),
):
    data = autofill_service.autofill_for_subject(db, current_user, subject_id)
    return {"found": data is not None, "custom_fields": data or {}}
