"""
Employee Performance Service — Computes and serves per-employee metrics,
team performance, and leaderboards for supervisor dashboards.
"""
from datetime import date, datetime, timedelta, timezone

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.employee_performance import EmployeePerformance
from app.models.grievance import Grievance
from app.models.interaction import ChatSession, Message
from app.models.task import Task
from app.models.user import Employee

logger = structlog.get_logger()


class PerformanceService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_employee_performance(
        self, employee_id: int, period_type: str = "weekly", periods: int = 4
    ) -> list[dict]:
        """Get employee performance for the last N periods."""
        result = await self.db.execute(
            select(EmployeePerformance)
            .where(EmployeePerformance.employee_id == employee_id)
            .where(EmployeePerformance.period_type == period_type)
            .order_by(EmployeePerformance.period_start.desc())
            .limit(periods)
        )
        records = result.scalars().all()

        return [
            {
                "period_start": str(r.period_start),
                "period_type": r.period_type,
                "grievances_filed": r.grievances_filed,
                "grievances_resolved": r.grievances_resolved,
                "avg_resolution_hours": float(r.avg_resolution_hours) if r.avg_resolution_hours else None,
                "sla_compliance_pct": float(r.sla_compliance_pct) if r.sla_compliance_pct else None,
                "tasks_completed": r.tasks_completed,
                "tasks_overdue": r.tasks_overdue,
                "task_completion_rate": float(r.task_completion_rate) if r.task_completion_rate else None,
                "scheme_queries_handled": r.scheme_queries_handled,
                "forms_processed": r.forms_processed,
                "total_time_saved_minutes": float(r.total_time_saved_minutes) if r.total_time_saved_minutes else None,
            }
            for r in records
        ]

    async def get_team_performance(
        self, secretariat_id: int, period_type: str = "weekly"
    ) -> dict:
        """Get team performance for a secretariat."""
        result = await self.db.execute(
            select(EmployeePerformance)
            .join(Employee, EmployeePerformance.employee_id == Employee.id)
            .where(Employee.secretariat_id == secretariat_id)
            .where(EmployeePerformance.period_type == period_type)
            .order_by(EmployeePerformance.period_start.desc())
            .limit(50)
        )
        records = result.scalars().all()

        if not records:
            return {"secretariat_id": secretariat_id, "employees": [], "totals": {}}

        totals = {
            "grievances_resolved": sum(r.grievances_resolved for r in records),
            "tasks_completed": sum(r.tasks_completed for r in records),
            "forms_processed": sum(r.forms_processed for r in records),
        }

        return {
            "secretariat_id": secretariat_id,
            "period_type": period_type,
            "employee_count": len(set(r.employee_id for r in records)),
            "totals": totals,
        }

    async def get_leaderboard(
        self, metric: str = "grievances_resolved", period_type: str = "monthly", limit: int = 10
    ) -> list[dict]:
        """Get leaderboard ranked by a specific metric."""
        metric_column = getattr(EmployeePerformance, metric, None)
        if metric_column is None:
            metric_column = EmployeePerformance.grievances_resolved

        result = await self.db.execute(
            select(
                EmployeePerformance.employee_id,
                Employee.name_te,
                Employee.name_en,
                Employee.designation,
                func.sum(metric_column).label("metric_value"),
            )
            .join(Employee, EmployeePerformance.employee_id == Employee.id)
            .where(EmployeePerformance.period_type == period_type)
            .group_by(
                EmployeePerformance.employee_id,
                Employee.name_te,
                Employee.name_en,
                Employee.designation,
            )
            .order_by(func.sum(metric_column).desc())
            .limit(limit)
        )
        rows = result.all()

        return [
            {
                "rank": i + 1,
                "employee_id": row.employee_id,
                "name_te": row.name_te,
                "name_en": row.name_en,
                "designation": row.designation,
                "metric_value": float(row.metric_value) if row.metric_value else 0,
            }
            for i, row in enumerate(rows)
        ]

    async def compute_daily_performance(self, employee_id: int, target_date: date) -> None:
        """Compute and store daily performance metrics for an employee."""
        start = datetime.combine(target_date, datetime.min.time()).replace(tzinfo=timezone.utc)
        end = start + timedelta(days=1)

        # Grievance metrics
        grievances_filed = (await self.db.execute(
            select(func.count()).where(
                Grievance.filed_by_employee_id == employee_id,
                Grievance.created_at >= start,
                Grievance.created_at < end,
            )
        )).scalar() or 0

        grievances_resolved = (await self.db.execute(
            select(func.count()).where(
                Grievance.filed_by_employee_id == employee_id,
                Grievance.resolved_at >= start,
                Grievance.resolved_at < end,
            )
        )).scalar() or 0

        # Task metrics
        tasks_completed = (await self.db.execute(
            select(func.count()).where(
                Task.employee_id == employee_id,
                Task.status == "completed",
                Task.completed_at >= start,
                Task.completed_at < end,
            )
        )).scalar() or 0

        tasks_overdue = (await self.db.execute(
            select(func.count()).where(
                Task.employee_id == employee_id,
                Task.status.in_(["pending", "overdue"]),
                Task.due_date < target_date,
            )
        )).scalar() or 0

        # Save or update
        existing = await self.db.execute(
            select(EmployeePerformance).where(
                EmployeePerformance.employee_id == employee_id,
                EmployeePerformance.period_start == target_date,
                EmployeePerformance.period_type == "daily",
            )
        )
        perf = existing.scalar_one_or_none()

        if perf:
            perf.grievances_filed = grievances_filed
            perf.grievances_resolved = grievances_resolved
            perf.tasks_completed = tasks_completed
            perf.tasks_overdue = tasks_overdue
        else:
            perf = EmployeePerformance(
                employee_id=employee_id,
                period_type="daily",
                period_start=target_date,
                grievances_filed=grievances_filed,
                grievances_resolved=grievances_resolved,
                tasks_completed=tasks_completed,
                tasks_overdue=tasks_overdue,
            )
            self.db.add(perf)

        await self.db.flush()
