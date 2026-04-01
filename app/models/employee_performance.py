"""
Employee Performance model — Tracks per-employee metrics across
grievances, tasks, and citizen interactions for supervisor dashboards.
"""
from datetime import date

from sqlalchemy import Date, ForeignKey, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class EmployeePerformance(Base):
    __tablename__ = "employee_performance"
    __table_args__ = (UniqueConstraint("employee_id", "period_start", "period_type"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id"), nullable=False)
    period_type: Mapped[str] = mapped_column(String(10), nullable=False)
    # daily, weekly, monthly
    period_start: Mapped[date] = mapped_column(Date, nullable=False)

    # Grievance metrics
    grievances_filed: Mapped[int] = mapped_column(Integer, default=0)
    grievances_resolved: Mapped[int] = mapped_column(Integer, default=0)
    avg_resolution_hours: Mapped[float | None] = mapped_column(Numeric(8, 1))
    avg_citizen_satisfaction: Mapped[float | None] = mapped_column(Numeric(3, 1))
    sla_compliance_pct: Mapped[float | None] = mapped_column(Numeric(5, 2))

    # Task metrics
    tasks_completed: Mapped[int] = mapped_column(Integer, default=0)
    tasks_overdue: Mapped[int] = mapped_column(Integer, default=0)
    task_completion_rate: Mapped[float | None] = mapped_column(Numeric(5, 2))
    avg_task_minutes: Mapped[float | None] = mapped_column(Numeric(8, 1))

    # Interaction metrics
    scheme_queries_handled: Mapped[int] = mapped_column(Integer, default=0)
    forms_processed: Mapped[int] = mapped_column(Integer, default=0)
    voice_minutes_handled: Mapped[float | None] = mapped_column(Numeric(8, 2))

    # Efficiency
    avg_response_time_seconds: Mapped[float | None] = mapped_column(Numeric(10, 2))
    total_time_saved_minutes: Mapped[float | None] = mapped_column(Numeric(10, 2))
