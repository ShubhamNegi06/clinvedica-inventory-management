"""Field definitions route — powers dynamic form rendering + section ordering on the frontend."""
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import require_any_role
from app.db.session import get_db
from app.models.field_definition import FieldDefinition
from app.models.user import User
from pydantic import BaseModel
import uuid


class FieldDefinitionRead(BaseModel):
    id: uuid.UUID
    field_key: str
    field_label: str
    section: str
    field_type: str
    display_order: int
    is_autofill: bool

    class Config:
        from_attributes = True


router = APIRouter(prefix="/field-definitions", tags=["field-definitions"])


@router.get("", response_model=list[FieldDefinitionRead])
def list_field_definitions(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_any_role),
):
    stmt = (
        select(FieldDefinition)
        .where(FieldDefinition.is_active.is_(True))
        .order_by(FieldDefinition.section, FieldDefinition.display_order)
    )
    return list(db.execute(stmt).scalars().all())
