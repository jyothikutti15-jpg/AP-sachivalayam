from datetime import date

from sqlalchemy import Date, ForeignKey, Integer, Numeric, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class DailyMetric(Base):
    __tablename__ = "daily_metrics"
    __table_args__ = (UniqueConstraint("employee_id", "date"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id"), nullable=False)
    date: Mapped[date] = mapped_column(Date, nullable=False)
    queries_handled: Mapped[int] = mapped_column(Integer, default=0)
    voice_minutes_saved: Mapped[float] = mapped_column(Numeric(8, 2), default=0)
    forms_auto_filled: Mapped[int] = mapped_column(Integer, default=0)
    manual_forms_estimated: Mapped[int] = mapped_column(Integer, default=0)
    time_saved_minutes: Mapped[float] = mapped_column(Numeric(8, 2), default=0)
    session_count: Mapped[int] = mapped_column(Integer, default=0)
    avg_response_time_ms: Mapped[int | None] = mapped_column(Integer)


class BurnoutIndicator(Base):
    __tablename__ = "burnout_indicators"
    __table_args__ = (UniqueConstraint("secretariat_id", "week_start"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    secretariat_id: Mapped[int] = mapped_column(ForeignKey("secretariats.id"), nullable=False)
    week_start: Mapped[date] = mapped_column(Date, nullable=False)
    avg_daily_hours_before: Mapped[float | None] = mapped_column(Numeric(4, 1))
    avg_daily_hours_with_copilot: Mapped[float | None] = mapped_column(Numeric(4, 1))
    repetitive_queries_automated: Mapped[int | None] = mapped_column(Integer)
    employee_satisfaction_score: Mapped[float | None] = mapped_column(Numeric(3, 1))
    citizen_wait_time_reduction_pct: Mapped[float | None] = mapped_column(Numeric(5, 2))
