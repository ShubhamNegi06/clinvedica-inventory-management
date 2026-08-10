"""
Excel export. Reuses the same filtering logic as the list endpoint
(sample_service.list_samples with page_size effectively unbounded) so
"export what I'm currently viewing" behaves identically to what's on
screen, rather than drifting from it via a separately-written query.
"""
import io
import uuid
from typing import List, Optional

from openpyxl import Workbook
from openpyxl.styles import Font
from sqlalchemy.orm import Session

from app.models.field_definition import FieldDefinition, SECTION_ORDER
from app.models.user import User
from app.services import sample_service


def _ordered_custom_field_keys(db: Session) -> List[str]:
    """Field order matches the canonical section ordering (Case Details ->
    ... -> Biomarker Characterization) so exports read the same way the
    add-sample form is laid out on the frontend."""
    field_defs = (
        db.query(FieldDefinition)
        .filter(FieldDefinition.is_active.is_(True))
        .order_by(FieldDefinition.section, FieldDefinition.display_order)
        .all()
    )
    section_rank = {s: i for i, s in enumerate(SECTION_ORDER)}
    field_defs.sort(key=lambda fd: (section_rank.get(fd.section, 999), fd.display_order))
    return [fd.field_key for fd in field_defs]


def export_samples_to_excel(
    db: Session,
    current_user: User,
    *,
    site_id: Optional[uuid.UUID] = None,
    tags: Optional[List[str]] = None,
    search: Optional[str] = None,
) -> io.BytesIO:
    # page_size capped high but bounded — protects against an accidental
    # export of an unbounded dataset locking up a worker process.
    items, _total = sample_service.list_samples(
        db, current_user, site_id=site_id, tags=tags, search=search, page=1, page_size=10000
    )

    custom_keys = _ordered_custom_field_keys(db)

    wb = Workbook()
    ws = wb.active
    ws.title = "Samples"

    fixed_headers = ["Site ID", "Subject Code", "Sample Code", "Sample Type", "Tags"]
    headers = fixed_headers + custom_keys
    ws.append(headers)
    for cell in ws[1]:
        cell.font = Font(bold=True)

    for sample in items:
        row = [
            str(sample.site_id),
            sample.subject_id,
            sample.sample_id,
            sample.sample_type.value if sample.sample_type else "",
            ", ".join(sample.tags or []),
        ]
        row += [sample.custom_fields.get(key, "") for key in custom_keys]
        ws.append(row)

    for col in ws.columns:
        max_len = max((len(str(c.value)) for c in col if c.value is not None), default=10)
        ws.column_dimensions[col[0].column_letter].width = min(max_len + 2, 50)

    buffer = io.BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    return buffer
