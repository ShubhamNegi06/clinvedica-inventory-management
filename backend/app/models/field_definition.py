"""
FieldDefinition model.

Mirrors the v1 canonical field ordering system (lib/fieldOrder.ts /
lib/sections.ts on the frontend). Kept server-side as the single source of
truth so the frontend section ordering and the autofill/suggestion logic
never drift apart.
"""
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


# Canonical section order — matches v1 exactly.
SECTION_ORDER = [
    "case_details",
    "demographic_details",
    "diagnosis_information",
    "sample_information",
    "serology_report",
    "treatment_detail",
    "biomarker_characterization",
]


# Human-readable section titles, matching the Excel template exactly.
# Single source of truth reused by both the export service (to write the
# template's section-title row) and could be reused by any future
# section-label needs server-side.
SECTION_LABELS = {
    "case_details": "Case Details",
    "demographic_details": "Demographic Details",
    "diagnosis_information": "Diagnosis Information",
    "sample_information": "Sample Information",
    "serology_report": "Serology Report",
    "treatment_detail": "Treatment Detail",
    "biomarker_characterization": "Biomarker Characterization",
}


class FieldDefinition(Base):
    __tablename__ = "field_definitions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # kebab-case key used inside Sample.custom_fields, e.g. "tumor-grade"
    field_key: Mapped[str] = mapped_column(String(150), nullable=False)
    field_label: Mapped[str] = mapped_column(String(255), nullable=False)  # human-readable display text
    section: Mapped[str] = mapped_column(String(50), nullable=False)
    field_type: Mapped[str] = mapped_column(String(30), default="text")  # text | number | date | select
    display_order: Mapped[int] = mapped_column(Integer, default=0)

    # Whether this field should be pre-filled when a matching subject_code
    # is found (see the Subject ID Autofill feature).
    is_autofill: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (UniqueConstraint("field_key", name="uq_field_definition_key"),)

    def __repr__(self) -> str:
        return f"<FieldDefinition {self.field_key} section={self.section}>"
