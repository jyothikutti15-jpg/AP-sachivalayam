"""
Task models — Tracks employee tasks across 34 departments,
enables AI-powered daily prioritization to reduce burnout.
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
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class Task(Base, TimestampMixin):
    __tablename__ = "tasks"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    employee_id: Mapped[int] = mapped_column(
        ForeignKey("employees.id"), nullable=False
    )
    secretariat_id: Mapped[int | None] = mapped_column(ForeignKey("secretariats.id"))

    # Task details
    title_te: Mapped[str] = mapped_column(Text, nullable=False)
    title_en: Mapped[str | None] = mapped_column(Text)
    description_te: Mapped[str | None] = mapped_column(Text)
    description_en: Mapped[str | None] = mapped_column(Text)

    # Classification
    department: Mapped[str] = mapped_column(String(100), nullable=False)
    category: Mapped[str] = mapped_column(String(50), default="general")
    # categories: scheme_processing, field_visit, data_entry, report_writing,
    #             grievance_followup, meeting, survey, inspection, citizen_service

    # Priority and scheduling
    priority: Mapped[str] = mapped_column(String(10), default="medium")
    # low, medium, high, urgent
    priority_score: Mapped[int] = mapped_column(SmallInteger, default=50)
    # 0-100, computed by AI prioritization engine

    due_date: Mapped[date | None] = mapped_column(Date)
    estimated_minutes: Mapped[int] = mapped_column(Integer, default=30)

    # Status
    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)
    # pending -> in_progress -> completed / skipped / overdue
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    actual_minutes: Mapped[int | None] = mapped_column(Integer)

    # Source — where did this task come from?
    source: Mapped[str] = mapped_column(String(20), default="manual")
    # manual, gsws_sync, grievance, scheme_processing, recurring, ai_suggested
    source_reference_id: Mapped[str | None] = mapped_column(String(50))
    # e.g., grievance UUID, scheme application ID

    # AI prioritization metadata
    ai_priority_reason_te: Mapped[str | None] = mapped_column(Text)
    ai_priority_reason_en: Mapped[str | None] = mapped_column(Text)
    is_ai_suggested: Mapped[bool] = mapped_column(Boolean, default=False)

    # Recurrence
    is_recurring: Mapped[bool] = mapped_column(Boolean, default=False)
    recurrence_rule: Mapped[str | None] = mapped_column(String(50))
    # daily, weekly, monthly, first_monday, last_friday, etc.

    metadata_extra: Mapped[dict | None] = mapped_column(JSONB)


class DailyPlan(Base):
    """AI-generated daily task plan for an employee."""

    __tablename__ = "daily_plans"
    __table_args__ = (UniqueConstraint("employee_id", "plan_date"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    employee_id: Mapped[int] = mapped_column(
        ForeignKey("employees.id"), nullable=False
    )
    plan_date: Mapped[date] = mapped_column(Date, nullable=False)

    # Ordered list of task IDs with priority reasoning
    task_order: Mapped[dict] = mapped_column(JSONB, nullable=False)
    # [{"task_id": "uuid", "rank": 1, "reason_te": "...", "estimated_minutes": 30}, ...]

    total_estimated_minutes: Mapped[int] = mapped_column(Integer, default=0)
    ai_summary_te: Mapped[str | None] = mapped_column(Text)
    ai_summary_en: Mapped[str | None] = mapped_column(Text)

    # Was the plan sent to the employee?
    sent_via_whatsapp: Mapped[bool] = mapped_column(Boolean, default=False)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
