"""Schemas for the Supervisor Dashboard API."""
from pydantic import BaseModel


class GrievanceStats(BaseModel):
    total: int = 0
    resolved: int = 0
    open: int = 0
    sla_breached: int = 0
    resolution_rate: float = 0.0


class TaskStats(BaseModel):
    total: int = 0
    completed: int = 0
    pending: int = 0
    completion_rate: float = 0.0


class MandalOverview(BaseModel):
    mandal: str
    period_days: int
    secretariat_count: int
    employee_count: int
    grievances: GrievanceStats
    tasks: TaskStats


class DistrictOverview(BaseModel):
    district: str
    period_days: int
    mandal_count: int
    secretariat_count: int
    employee_count: int
    grievances: GrievanceStats


class SecretariatRanking(BaseModel):
    secretariat_id: int
    secretariat_name: str
    gsws_code: str
    metric: str
    value: int | float


class SLAAlert(BaseModel):
    grievance_id: str
    reference_number: str
    citizen_name: str
    category: str
    department: str
    priority: str
    status: str
    sla_deadline: str
    hours_overdue: float
    escalation_level: int
    filed_at: str


class SLAAlertListResponse(BaseModel):
    alerts: list[SLAAlert]
    total: int


class LowPerformingSecretariat(BaseModel):
    secretariat_id: int
    secretariat_name: str
    gsws_code: str
    mandal: str
    task_completion_rate: float
    total_tasks: int
    completed_tasks: int


class EmployeeDetail(BaseModel):
    employee_id: int
    name_te: str
    name_en: str | None = None
    designation: str
    department: str
    role: str
    open_grievances: int
    pending_tasks: int
    performance: dict | None = None
