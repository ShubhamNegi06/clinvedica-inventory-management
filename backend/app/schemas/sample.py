"""Pydantic request/response schemas for Sample endpoints."""
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from app.models.enums import SampleType


class SampleCreate(BaseModel):
    site_id: uuid.UUID
    subject_id: str = Field(..., min_length=1, max_length=100)
    sample_id: str = Field(..., min_length=1, max_length=150)
    sample_type: Optional[SampleType] = None
    tags: List[str] = Field(default_factory=list)
    custom_fields: Dict[str, Any] = Field(default_factory=dict)


class SampleUpdate(BaseModel):
    subject_id: Optional[str] = Field(default=None, min_length=1, max_length=100)
    sample_id: Optional[str] = Field(default=None, min_length=1, max_length=150)
    sample_type: Optional[SampleType] = None
    tags: Optional[List[str]] = None
    custom_fields: Optional[Dict[str, Any]] = None


class SampleRead(BaseModel):
    id: uuid.UUID
    site_id: uuid.UUID
    subject_id: str
    sample_id: str
    sample_type: Optional[SampleType]
    tags: List[str]
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
