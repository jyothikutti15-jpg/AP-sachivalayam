from datetime import date

from pydantic import BaseModel


class SecretariatSummaryResponse(BaseModel):
    secretariat_id: int
    secretariat_name: str
    period_start: date
    period_end: date
    total_queries: int = 0
    total_forms_filled: int = 0
    total_time_saved_hours: float = 0.0
    active_employees: int = 0
    top_schemes_queried: list[dict] = []


class BurnoutReportResponse(BaseModel):
    secretariat_id: int
    secretariat_name: str
    week_start: date
    avg_daily_hours_before: float | None = None
    avg_daily_hours_with_copilot: float | None = None
    hours_reduction_pct: float | None = None
    repetitive_queries_automated: int | None = None
    employee_satisfaction_score: float | None = None


class TimeSavedResponse(BaseModel):
    period_start: date
    period_end: date
    total_time_saved_hours: float = 0.0
    total_forms_auto_filled: int = 0
    total_queries_handled: int = 0
    total_employees_served: int = 0
    projected_annual_hours_saved: float = 0.0
    projected_cost_savings_inr: float = 0.0
