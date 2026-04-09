"""Outreach model — Tracks scheme outreach to eligible beneficiaries."""
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class OutreachRecord(Base, TimestampMixin):
    __tablename__ = "outreach_records"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    beneficiary_id: Mapped[int] = mapped_column(ForeignKey("beneficiaries.id"), nullable=False)
    scheme_code: Mapped[str] = mapped_column(String(50), nullable=False)
    secretariat_id: Mapped[int | None] = mapped_column(ForeignKey("secretariats.id"))
    matched_by_employee_id: Mapped[int | None] = mapped_column(ForeignKey("employees.id"))
    match_score: Mapped[float] = mapped_column(Float, default=0.0)
    match_reasoning_te: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="identified")
    # Status: identified -> notified -> applied -> enrolled | rejected
    notified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    applied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
