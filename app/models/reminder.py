"""
Reminder models — Tracks scheduled follow-up reminders for citizens.
Auto-sends WhatsApp reminders for pending documents, renewals, and disbursements.
"""

import uuid
from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    SmallInteger,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class CitizenReminder(Base, TimestampMixin):
    """A scheduled follow-up reminder for a citizen."""

    __tablename__ = "citizen_reminders"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    # Who created this reminder
    employee_id: Mapped[int] = mapped_column(
        ForeignKey("employees.id"), nullable=False
    )
    secretariat_id: Mapped[int | None] = mapped_column(ForeignKey("secretariats.id"))

    # Citizen details
    citizen_name: Mapped[str] = mapped_column(Text, nullable=False)
    citizen_phone: Mapped[str] = mapped_column(String(15), nullable=False)
    citizen_aadhaar_hash: Mapped[str | None] = mapped_column(String(64))

    # Reminder details
    reminder_type: Mapped[str] = mapped_column(String(30), nullable=False)
    # pending_documents, renewal_deadline, disbursement_date,
    # application_followup, scheme_deadline, general

    scheme_code: Mapped[str | None] = mapped_column(String(50))
    scheme_name_te: Mapped[str | None] = mapped_column(Text)

    # The message to send
    message_te: Mapped[str] = mapped_column(Text, nullable=False)
    message_en: Mapped[str | None] = mapped_column(Text)

    # What documents or actions are pending
    pending_items: Mapped[dict | None] = mapped_column(JSONB)
    # e.g., ["income_certificate", "caste_certificate"] or ["renewal form"]

    # Schedule
    reminder_date: Mapped[date] = mapped_column(Date, nullable=False)
    reminder_time: Mapped[str] = mapped_column(String(5), default="09:00")
    # HH:MM in IST

    # Recurrence
    is_recurring: Mapped[bool] = mapped_column(Boolean, default=False)
    recurrence_rule: Mapped[str | None] = mapped_column(String(30))
    # once, daily, weekly, monthly, before_deadline
    recurrence_end_date: Mapped[date | None] = mapped_column(Date)

    # Status
    status: Mapped[str] = mapped_column(String(20), default="scheduled", nullable=False)
    # scheduled, sent, acknowledged, completed, cancelled, failed

    # Delivery tracking
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # How many times this reminder has been sent (for recurring)
    send_count: Mapped[int] = mapped_column(Integer, default=0)
    max_sends: Mapped[int] = mapped_column(Integer, default=3)

    # Priority
    priority: Mapped[str] = mapped_column(String(10), default="medium")
    # low, medium, high, urgent

    # Linked references
    form_submission_id: Mapped[str | None] = mapped_column(String(50))
    grievance_reference: Mapped[str | None] = mapped_column(String(20))

    metadata_extra: Mapped[dict | None] = mapped_column(JSONB)
