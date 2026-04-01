from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel


class TaskCreateRequest(BaseModel):
    title_te: str
    title_en: str | None = None
    description_te: str | None = None
    department: str
    category: str = "general"
    priority: str = "medium"
    due_date: date | None = None
    estimated_minutes: int = 30
    is_recurring: bool = False
    recurrence_rule: str | None = None
    source: str = "manual"
    source_reference_id: str | None = None


class TaskResponse(BaseModel):
    id: UUID
    employee_id: int
    title_te: str
    title_en: str | None = None
    department: str
    category: str
    priority: str
    priority_score: int
    due_date: date | None = None
    estimated_minutes: int
    status: str
    started_at: datetime | None = None
    completed_at: datetime | None = None
    actual_minutes: int | None = None
    source: str
    ai_priority_reason_te: str | None = None
    is_ai_suggested: bool
    is_recurring: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class TaskUpdateRequest(BaseModel):
    status: str | None = None
    priority: str | None = None
    actual_minutes: int | None = None
    title_te: str | None = None
    due_date: date | None = None


class DailyPlanResponse(BaseModel):
    plan_date: date
    tasks: list["PrioritizedTask"]
    total_estimated_minutes: int
    ai_summary_te: str | None = None
    ai_summary_en: str | None = None


class PrioritizedTask(BaseModel):
    task_id: UUID
    rank: int
    title_te: str
    department: str
    priority: str
    priority_score: int
    due_date: date | None = None
    estimated_minutes: int
    status: str
    reason_te: str | None = None


class WorkloadSummaryResponse(BaseModel):
    employee_id: int
    date: date
    total_tasks: int
    completed_tasks: int
    overdue_tasks: int
    pending_tasks: int
    in_progress_tasks: int
    total_estimated_minutes: int
    total_actual_minutes: int
    departments_involved: list[str]
    workload_level: str  # light, moderate, heavy, overloaded
