"""
Sample model.

Field flexibility is handled via a JSONB `custom_fields` column (GIN
indexed) rather than an EAV table — this was a deliberate architecture
decision carried over from v1: it allows efficient arbitrary-key search
across sites without the join overhead of an EAV model. Canonical/known
fields (case details, demographics, diagnosis, sample info, etc.) all live
inside `custom_fields`, keyed by the kebab-case field keys defined in
`field_definitions`. A handful of fields are promoted to real columns
because they need DB-level constraints or are queried constantly:
subject_id, sample_id, sample_type, tags.
"""
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import ARRAY, Boolean, DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.models.enums import SampleType


class Sample(Base):
    __tablename__ = "samples"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    site_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sites.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # Groups multiple samples belonging to the same patient/subject —
    # this is what drives the subject-ID autofill feature.
    subject_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)

    # Unique per site (not globally) — two different sites may legitimately
    # use overlapping internal codes.
    sample_id: Mapped[str] = mapped_column(String(150), nullable=False, index=True)

    sample_type: Mapped[Optional[SampleType]] = mapped_column(String(30), nullable=True)

    # Tags drive the "Tag Filtering" feature — kept as a native Postgres
    # array (GIN-indexable) rather than inside custom_fields for fast
    # `ANY(tags)` filtering.
    tags: Mapped[List[str]] = mapped_column(ARRAY(String), default=list, server_default="{}")

    # All canonical section fields (case details, demographics, diagnosis,
    # sample info, serology, treatment, biomarker) live here, keyed by the
    # kebab-case field_key from field_definitions.
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
        # code may appear across different sites. This constraint is what
        # produces the structured 409 (via _handle_integrity_error in the
        # samples service), not a raw Postgres error.
        UniqueConstraint("site_id", "sample_id", name="uq_sample_site_code"),
    )

    def __repr__(self) -> str:
        return f"<Sample {self.sample_id} site={self.site_id}>"
