"""Schemas for Citizen Follow-up Reminders (Feature 10)."""

from datetime import date, datetime

from pydantic import BaseModel


class ReminderCreate(BaseModel):
    employee_id: int
    secretariat_id: int | None = None
    citizen_name: str
    citizen_phone: str
    reminder_type: str  # pending_documents, renewal_deadline, disbursement_date, etc.
    scheme_code: str | None = None
    message_te: str
    message_en: str | None = None
    pending_items: list[str] | None = None
    reminder_date: date
    reminder_time: str = "09:00"
    is_recurring: bool = False
    recurrence_rule: str | None = None  # once, daily, weekly, monthly
    recurrence_end_date: date | None = None
    priority: str = "medium"
    form_submission_id: str | None = None
    grievance_reference: str | None = None


class ReminderResponse(BaseModel):
    id: str
    employee_id: int
    citizen_name: str
    citizen_phone: str
    reminder_type: str
    scheme_code: str | None = None
    scheme_name_te: str | None = None
    message_te: str
    message_en: str | None = None
    pending_items: list[str] | None = None
    reminder_date: date
    reminder_time: str
    is_recurring: bool
    recurrence_rule: str | None = None
    status: str
    sent_at: datetime | None = None
    send_count: int = 0
    priority: str
    created_at: datetime | None = None

    model_config = {"from_attributes": True}


class ReminderUpdate(BaseModel):
    status: str | None = None  # cancelled, completed, acknowledged
    message_te: str | None = None
    reminder_date: date | None = None
    reminder_time: str | None = None
    priority: str | None = None


class ReminderStatsResponse(BaseModel):
    total_scheduled: int = 0
    total_sent: int = 0
    total_acknowledged: int = 0
    total_completed: int = 0
    total_failed: int = 0
    total_cancelled: int = 0
    by_type: dict = {}
    by_scheme: dict = {}


class AutoReminderRequest(BaseModel):
    """Auto-generate reminders from a form submission or scheme application."""
    citizen_name: str
    citizen_phone: str
    employee_id: int
    secretariat_id: int | None = None
    scheme_code: str
    missing_documents: list[str] = []
    deadline: date | None = None
