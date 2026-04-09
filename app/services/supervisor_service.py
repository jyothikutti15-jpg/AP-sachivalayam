"""Supervisor Service — Aggregate analytics for MPDO/Mandal/District officers."""
from datetime import datetime, timedelta, timezone

import structlog
from sqlalchemy import func, select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.grievance import Grievance
from app.models.task import Task
from app.models.user import Employee, Secretariat
from app.models.analytics import DailyMetric
from app.models.employee_performance import EmployeePerformance

logger = structlog.get_logger()


class SupervisorService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_mandal_overview(self, mandal: str, days: int = 30) -> dict:
        """Aggregate stats across all secretariats in a mandal."""
        since = datetime.now(timezone.utc) - timedelta(days=days)

        # Get secretariats in mandal
        sec_result = await self.db.execute(
            select(Secretariat).where(Secretariat.mandal == mandal)
        )
        secretariats = sec_result.scalars().all()
        sec_ids = [s.id for s in secretariats]

        if not sec_ids:
            return {"mandal": mandal, "secretariat_count": 0, "error": "No secretariats found"}

        # Grievance stats
        grv_result = await self.db.execute(
            select(
                func.count(Grievance.id).label("total"),
                func.count().filter(Grievance.status == "resolved").label("resolved"),
                func.count().filter(Grievance.status == "open").label("open"),
                func.count().filter(
                    and_(Grievance.sla_deadline < datetime.now(timezone.utc),
                         Grievance.status.in_(["open", "acknowledged", "in_progress"]))
                ).label("sla_breached"),
            ).where(
                and_(Grievance.secretariat_id.in_(sec_ids), Grievance.created_at >= since)
            )
        )
        grv_stats = grv_result.one()

        # Task stats
        task_result = await self.db.execute(
            select(
                func.count(Task.id).label("total"),
                func.count().filter(Task.status == "completed").label("completed"),
                func.count().filter(Task.status.in_(["pending", "overdue"])).label("pending"),
            ).where(
                and_(Task.secretariat_id.in_(sec_ids), Task.created_at >= since)
            )
        )
        task_stats = task_result.one()

        # Employee count
        emp_count = await self.db.execute(
            select(func.count(Employee.id)).where(Employee.secretariat_id.in_(sec_ids))
        )

        return {
            "mandal": mandal,
            "period_days": days,
            "secretariat_count": len(secretariats),
            "employee_count": emp_count.scalar() or 0,
            "grievances": {
                "total": grv_stats.total or 0,
                "resolved": grv_stats.resolved or 0,
                "open": grv_stats.open or 0,
                "sla_breached": grv_stats.sla_breached or 0,
                "resolution_rate": round((grv_stats.resolved / grv_stats.total * 100) if grv_stats.total else 0, 1),
            },
            "tasks": {
                "total": task_stats.total or 0,
                "completed": task_stats.completed or 0,
                "pending": task_stats.pending or 0,
                "completion_rate": round((task_stats.completed / task_stats.total * 100) if task_stats.total else 0, 1),
            },
        }

    async def get_district_overview(self, district: str, days: int = 30) -> dict:
        """District-level aggregate stats."""
        since = datetime.now(timezone.utc) - timedelta(days=days)

        sec_result = await self.db.execute(
            select(Secretariat).where(Secretariat.district == district)
        )
        secretariats = sec_result.scalars().all()
        sec_ids = [s.id for s in secretariats]
        mandals = list(set(s.mandal for s in secretariats))

        if not sec_ids:
            return {"district": district, "secretariat_count": 0, "error": "No secretariats found"}

        grv_result = await self.db.execute(
            select(
                func.count(Grievance.id).label("total"),
                func.count().filter(Grievance.status == "resolved").label("resolved"),
                func.count().filter(
                    and_(Grievance.sla_deadline < datetime.now(timezone.utc),
                         Grievance.status.in_(["open", "acknowledged", "in_progress"]))
                ).label("sla_breached"),
            ).where(and_(Grievance.secretariat_id.in_(sec_ids), Grievance.created_at >= since))
        )
        grv_stats = grv_result.one()

        emp_count = await self.db.execute(
            select(func.count(Employee.id)).where(Employee.secretariat_id.in_(sec_ids))
        )

        return {
            "district": district,
            "period_days": days,
            "mandal_count": len(mandals),
            "secretariat_count": len(secretariats),
            "employee_count": emp_count.scalar() or 0,
            "grievances": {
                "total": grv_stats.total or 0,
                "resolved": grv_stats.resolved or 0,
                "sla_breached": grv_stats.sla_breached or 0,
                "resolution_rate": round((grv_stats.resolved / grv_stats.total * 100) if grv_stats.total else 0, 1),
            },
        }

    async def get_secretariat_rankings(self, mandal: str, metric: str = "grievances_resolved", limit: int = 20) -> list[dict]:
        """Rank secretariats in a mandal by performance metric."""
        sec_result = await self.db.execute(
            select(Secretariat).where(Secretariat.mandal == mandal)
        )
        secretariats = sec_result.scalars().all()

        rankings = []
        for sec in secretariats:
            # Get aggregated performance for this secretariat
            metric_col = getattr(EmployeePerformance, metric, EmployeePerformance.grievances_resolved)
            perf_result = await self.db.execute(
                select(
                    func.sum(metric_col).label("metric_value"),
                ).where(
                    EmployeePerformance.employee_id.in_(
                        select(Employee.id).where(Employee.secretariat_id == sec.id)
                    )
                )
            )
            val = perf_result.scalar() or 0
            rankings.append({
                "secretariat_id": sec.id,
                "secretariat_name": sec.name_en,
                "gsws_code": sec.gsws_code,
                "metric": metric,
                "value": val,
            })

        rankings.sort(key=lambda x: x["value"], reverse=True)
        return rankings[:limit]

    async def get_sla_breach_alerts(
        self, mandal: str | None = None, district: str | None = None, limit: int = 50, offset: int = 0
    ) -> tuple[list[dict], int]:
        """Get grievances that have breached SLA deadline."""
        now = datetime.now(timezone.utc)
        query = select(Grievance).where(
            and_(
                Grievance.sla_deadline < now,
                Grievance.status.in_(["open", "acknowledged", "in_progress"]),
            )
        )

        if mandal or district:
            sec_query = select(Secretariat.id)
            if mandal:
                sec_query = sec_query.where(Secretariat.mandal == mandal)
            if district:
                sec_query = sec_query.where(Secretariat.district == district)
            query = query.where(Grievance.secretariat_id.in_(sec_query))

        count_q = select(func.count()).select_from(query.subquery())
        total = (await self.db.execute(count_q)).scalar() or 0

        query = query.order_by(Grievance.sla_deadline.asc()).offset(offset).limit(limit)
        result = await self.db.execute(query)
        grievances = result.scalars().all()

        alerts = []
        for g in grievances:
            hours_overdue = (now - g.sla_deadline).total_seconds() / 3600
            alerts.append({
                "grievance_id": str(g.id),
                "reference_number": g.reference_number,
                "citizen_name": g.citizen_name,
                "category": g.category,
                "department": g.department,
                "priority": g.priority,
                "status": g.status,
                "sla_deadline": g.sla_deadline.isoformat(),
                "hours_overdue": round(hours_overdue, 1),
                "escalation_level": g.escalation_level,
                "filed_at": g.created_at.isoformat(),
            })

        return alerts, total

    async def get_low_performing_secretariats(
        self, district: str, threshold_completion_rate: float = 50.0
    ) -> list[dict]:
        """Find secretariats with task/grievance completion rate below threshold."""
        sec_result = await self.db.execute(
            select(Secretariat).where(Secretariat.district == district)
        )
        secretariats = sec_result.scalars().all()

        low_performers = []
        for sec in secretariats:
            # Task completion rate
            task_result = await self.db.execute(
                select(
                    func.count(Task.id).label("total"),
                    func.count().filter(Task.status == "completed").label("completed"),
                ).where(Task.secretariat_id == sec.id)
            )
            stats = task_result.one()
            rate = (stats.completed / stats.total * 100) if stats.total else 100.0

            if rate < threshold_completion_rate:
                low_performers.append({
                    "secretariat_id": sec.id,
                    "secretariat_name": sec.name_en,
                    "gsws_code": sec.gsws_code,
                    "mandal": sec.mandal,
                    "task_completion_rate": round(rate, 1),
                    "total_tasks": stats.total or 0,
                    "completed_tasks": stats.completed or 0,
                })

        low_performers.sort(key=lambda x: x["task_completion_rate"])
        return low_performers

    async def get_employee_detail(self, employee_id: int) -> dict | None:
        """Detailed view of a single employee's activity."""
        emp_result = await self.db.execute(
            select(Employee).where(Employee.id == employee_id)
        )
        employee = emp_result.scalar_one_or_none()
        if not employee:
            return None

        # Performance data (latest by period_start)
        perf_result = await self.db.execute(
            select(EmployeePerformance)
            .where(EmployeePerformance.employee_id == employee_id)
            .order_by(EmployeePerformance.period_start.desc())
            .limit(1)
        )
        perf = perf_result.scalar_one_or_none()

        # Open grievances
        open_grv = await self.db.execute(
            select(func.count(Grievance.id)).where(
                and_(Grievance.filed_by_employee_id == employee_id,
                     Grievance.status.in_(["open", "acknowledged", "in_progress"]))
            )
        )

        # Pending tasks
        pending_tasks = await self.db.execute(
            select(func.count(Task.id)).where(
                and_(Task.employee_id == employee_id,
                     Task.status.in_(["pending", "in_progress", "overdue"]))
            )
        )

        return {
            "employee_id": employee.id,
            "name_te": employee.name_te,
            "name_en": employee.name_en,
            "designation": employee.designation,
            "department": employee.department,
            "role": employee.role,
            "open_grievances": open_grv.scalar() or 0,
            "pending_tasks": pending_tasks.scalar() or 0,
            "performance": {
                "grievances_filed": perf.grievances_filed if perf else 0,
                "grievances_resolved": perf.grievances_resolved if perf else 0,
                "tasks_completed": perf.tasks_completed if perf else 0,
                "forms_processed": perf.forms_processed if perf else 0,
                "time_saved_minutes": float(perf.total_time_saved_minutes) if perf and perf.total_time_saved_minutes else 0,
            } if perf else None,
        }
