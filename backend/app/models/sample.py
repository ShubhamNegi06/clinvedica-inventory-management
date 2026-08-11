"""
Sample model.

Field flexibility is handled via a JSONB `custom_fields` column (GIN
indexed) rather than an EAV table — this was a deliberate architecture
decision carried over from v1: it allows efficient arbitrary-key search
across sites without the join overhead of an EAV model. EVERY field from
the Clinvedica Excel template (Type of Tissue, Age, Gender, Grade, Stage,
Sample Type, Tumor %, HIV/HBV/HCV, etc.) lives inside `custom_fields`,
keyed by the kebab-case field keys defined in `field_definitions` — none
of them are invented enum columns. Only `subject_id` and `sample_id`
(the template's "Subject ID" / "Sample ID" columns) are promoted to real
columns, because they need DB-level uniqueness/indexing.

NOTE: earlier versions of this model had a `sample_type` enum column
(FFPE/frozen/serum/...) and a `tags` array column. Neither exists in the
real template — "Type of Tissue" and "Sample Type" are free-text fields
in the template, not a fixed set we should be constraining, and tag
filtering was replaced with structured key:value field filtering
(filtering directly on custom_fields, see sample_service.list_samples).
Both were removed in migration 0002_align_with_template.
"""
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class Sample(Base):
    __tablename__ = "samples"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    site_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sites.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # Matches the template's "Subject ID" column. Groups multiple samples
    # belonging to the same patient/subject — this is what drives the
    # subject-ID autofill feature.
    subject_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)

    # Matches the template's "Sample ID" column. Unique per site (not
    # globally) — two different sites may legitimately use overlapping
    # internal IDs.
    sample_id: Mapped[str] = mapped_column(String(150), nullable=False, index=True)

    # Every other template column (Type of Tissue, Age, Gender, Ethnicity,
    # Country of Origin, Biopsy/Surgery, Diagnostic Procedure, Origin Site,
    # Diagnosis Result, Grade, Stage, T/N/M, Sample Type, dates, Fixation
    # Used, Tumor %/Necrosis %, Storage Temperature, HIV/HBV/HCV, Treatment
    # Information, Biomarker Details, plus Sample Category from which
    # sheet — Prospective/Remnant — a bulk-ingested row came from) lives
    # here, keyed by the kebab-case field_key from field_definitions.
    custom_fields: Mapped[Dict[str, Any]] = mapped_column(JSONB, default=dict, server_default="{}")

    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)

    created_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    updated_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    site: Mapped["Site"] = relationship("Site", back_populates="samples")
    reports: Mapped[List["Report"]] = relationship(
        "Report", back_populates="sample", cascade="all, delete-orphan"
    )

    __table_args__ = (
        # A sample_id must be unique within a given site, but the same
        # ID may appear across different sites. This constraint is what
        # produces the structured 409 in sample_service, not a raw
        # Postgres error.
        UniqueConstraint("site_id", "sample_id", name="uq_sample_site_sample_id"),
    )

    def __repr__(self) -> str:
        return f"<Sample {self.sample_id} site={self.site_id}>"
