"""
Audit Trail — Logs all actions on grievances, tasks, forms, and sensitive data
for government compliance and accountability.
"""
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class AuditLog(Base, TimestampMixin):
    __tablename__ = "audit_logs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    employee_id: Mapped[int | None] = mapped_column(
        ForeignKey("employees.id"), nullable=True
    )
    action: Mapped[str] = mapped_column(String(50), nullable=False)
    # create, update, delete, view, export, login, escalate, assign, resolve

    resource_type: Mapped[str] = mapped_column(String(50), nullable=False)
    # grievance, task, form, scheme, employee, session

    resource_id: Mapped[str] = mapped_column(String(50), nullable=False)
    # UUID or reference number

    old_values: Mapped[dict | None] = mapped_column(JSONB)
    new_values: Mapped[dict | None] = mapped_column(JSONB)

    ip_address: Mapped[str | None] = mapped_column(String(45))
    user_agent: Mapped[str | None] = mapped_column(String(200))
    status: Mapped[str] = mapped_column(String(10), default="success")
    error_message: Mapped[str | None] = mapped_column(Text)
