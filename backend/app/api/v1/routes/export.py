"""Excel export route — streams the generated workbook as a file download."""
import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.api.deps import require_any_role
from app.api.v1.routes.samples import _parse_field_filters
from app.db.session import get_db
from app.models.user import User
from app.services import export_service

router = APIRouter(prefix="/samples/export", tags=["samples"])


@router.get("")
def export_samples(
    site_id: Optional[uuid.UUID] = Query(default=None),
    field_filter: Optional[List[str]] = Query(default=None),
    search: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_any_role),
):
    buffer = export_service.export_samples_to_excel(
        db, current_user, site_id=site_id, field_filters=_parse_field_filters(field_filter), search=search
    )
    return StreamingResponse(
        buffer,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=specimen_inventory_export.xlsx"},
    )
