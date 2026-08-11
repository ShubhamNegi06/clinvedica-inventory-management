"""
Report model.

`report_type` + `original_report_id` implement the planned redaction
workflow: a masked report is a SEPARATE row linked back to its original
via `original_report_id`, rather than overwriting the original file. This
preserves the original for audit purposes while allowing access control
to differ between the two (e.g. clients/juniors only ever see 'masked').
"""
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import BigInteger, DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.models.enums import ReportType


class Report(Base):
    __tablename__ = "reports"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # FK to the sample row's UUID primary key — named sample_pk (not
    # sample_id) to avoid colliding with the business "Sample ID" field
    # that lives on Sample.sample_id (the template's "Sample ID" column).
    sample_pk: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("samples.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # Denormalized for fast permission checks / dashboard counts without a
    # join through samples on every report query.
    site_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sites.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # R2 object key — NOT a public URL. Access is always via a short-lived
    # signed URL minted on request (see app/services/storage.py).
    file_key: Mapped[str] = mapped_column(String(1024), nullable=False)
    file_name: Mapped[str] = mapped_column(String(500), nullable=False)
    file_size_bytes: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    content_type: Mapped[str] = mapped_column(String(150), default="application/pdf")

    report_type: Mapped[ReportType] = mapped_column(String(20), default=ReportType.ORIGINAL, nullable=False)
    original_report_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("reports.id", ondelete="SET NULL"), nullable=True
    )

    uploaded_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    sample: Mapped["Sample"] = relationship("Sample", back_populates="reports")

    def __repr__(self) -> str:
        return f"<Report {self.file_name} type={self.report_type}>"
