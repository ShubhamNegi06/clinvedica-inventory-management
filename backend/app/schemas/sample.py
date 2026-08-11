"""Pydantic request/response schemas for Sample endpoints."""
import uuid
from datetime import datetime
from typing import Any, Dict, List

from pydantic import BaseModel, Field


class SampleCreate(BaseModel):
    site_id: uuid.UUID
    subject_id: str = Field(..., min_length=1, max_length=100)
    sample_id: str = Field(..., min_length=1, max_length=150)
    custom_fields: Dict[str, Any] = Field(default_factory=dict)


class SampleUpdate(BaseModel):
    subject_id: str | None = Field(default=None, min_length=1, max_length=100)
    sample_id: str | None = Field(default=None, min_length=1, max_length=150)
    custom_fields: Dict[str, Any] | None = None


class SampleRead(BaseModel):
    id: uuid.UUID
    site_id: uuid.UUID
    subject_id: str
    sample_id: str
    custom_fields: Dict[str, Any]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class SampleListResponse(BaseModel):
    """Paginated list response — every list endpoint in this app returns this shape."""

    items: List[SampleRead]
    total: int
    page: int
    page_size: int
