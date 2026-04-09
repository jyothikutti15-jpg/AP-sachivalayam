"""Schemas for GO/Circular Knowledge Base (Feature 9)."""

from datetime import date

from pydantic import BaseModel


class CircularCreate(BaseModel):
    reference_number: str
    title_te: str
    title_en: str | None = None
    content_te: str | None = None
    content_en: str | None = None
    summary_te: str | None = None
    summary_en: str | None = None
    department: str
    category: str = "go"
    scheme_code: str | None = None
    issued_date: date
    effective_date: date | None = None
    expiry_date: date | None = None
    source_url: str | None = None
    pdf_url: str | None = None
    impact_level: str = "normal"
    key_changes: list[dict] | None = None
    affected_districts: list[str] | None = None
    tags: list[str] | None = None


class CircularResponse(BaseModel):
    id: str
    reference_number: str
    title_te: str
    title_en: str | None = None
    summary_te: str | None = None
    summary_en: str | None = None
    department: str
    category: str
    scheme_code: str | None = None
    issued_date: date
    effective_date: date | None = None
    impact_level: str
    key_changes: list[dict] | None = None
    tags: list[str] | None = None
    is_active: bool
    source_url: str | None = None

    model_config = {"from_attributes": True}


class CircularSearchRequest(BaseModel):
    query: str
    department: str | None = None
    scheme_code: str | None = None
    from_date: date | None = None
    to_date: date | None = None
    language: str = "te"


class CircularSearchResponse(BaseModel):
    answer: str
    circulars_referenced: list[CircularResponse] = []
    confidence: float = 0.0


class CircularSummaryRequest(BaseModel):
    """Request to auto-summarize a GO/circular using AI."""
    reference_number: str | None = None
    content_te: str | None = None
    content_en: str | None = None
