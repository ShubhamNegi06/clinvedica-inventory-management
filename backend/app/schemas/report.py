"""Pydantic request/response schemas for Report endpoints."""
import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel

from app.models.enums import ReportType


class ReportRead(BaseModel):
    id: uuid.UUID
    sample_id: uuid.UUID
    site_id: uuid.UUID
    file_name: str
    file_size_bytes: Optional[int]
    content_type: str
    report_type: ReportType
    original_report_id: Optional[uuid.UUID]
    created_at: datetime

    class Config:
        from_attributes = True


class ReportDownloadResponse(BaseModel):
    """A short-lived signed URL — never the raw object key or a public path."""

    url: str
    expires_in_seconds: int
