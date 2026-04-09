"""
Circular/GO models — Stores government orders and circulars for RAG search.
Employees can ask "What changed in Amma Vodi in March 2026?" and get answers.
"""

import uuid
from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class Circular(Base, TimestampMixin):
    """A government order (GO), circular, or official notification."""

    __tablename__ = "circulars"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    # GO / circular reference (e.g., "G.O.Ms.No.21")
    reference_number: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)

    title_te: Mapped[str] = mapped_column(Text, nullable=False)
    title_en: Mapped[str | None] = mapped_column(Text)

    content_te: Mapped[str | None] = mapped_column(Text)
    content_en: Mapped[str | None] = mapped_column(Text)

    # Summary for quick display
    summary_te: Mapped[str | None] = mapped_column(Text)
    summary_en: Mapped[str | None] = mapped_column(Text)

    # Classification
    department: Mapped[str] = mapped_column(String(100), nullable=False)
    category: Mapped[str] = mapped_column(String(50), default="go")
    # go, circular, memo, notification, amendment, proceedings

    # Related scheme (if this GO modifies a scheme)
    scheme_code: Mapped[str | None] = mapped_column(String(50))

    # Dates
    issued_date: Mapped[date] = mapped_column(Date, nullable=False)
    effective_date: Mapped[date | None] = mapped_column(Date)
    expiry_date: Mapped[date | None] = mapped_column(Date)

    # Source
    source_url: Mapped[str | None] = mapped_column(Text)
    pdf_url: Mapped[str | None] = mapped_column(Text)

    # Impact level for prioritization
    impact_level: Mapped[str] = mapped_column(String(20), default="normal")
    # critical, high, normal, low

    # Key changes (structured for quick reference)
    key_changes: Mapped[dict | None] = mapped_column(JSONB)
    # e.g., [{"field": "income_limit", "old": 200000, "new": 250000, "description_te": "..."}]

    affected_districts: Mapped[dict | None] = mapped_column(JSONB)
    # null = all districts, or ["Guntur", "Krishna", ...]

    tags: Mapped[dict | None] = mapped_column(JSONB)
    # ["eligibility_change", "new_scheme", "benefit_increase", ...]

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # View count for popularity tracking
    view_count: Mapped[int] = mapped_column(Integer, default=0)
