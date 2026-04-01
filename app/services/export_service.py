"""
Data Export Service — Exports grievance and task data as CSV
for government compliance reports.
"""
import csv
import io
from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.grievance import Grievance
from app.models.task import Task


class ExportService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def export_grievances_csv(
        self,
        secretariat_id: int | None = None,
        status: str | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> str:
        """Export grievances as CSV string."""
        query = select(Grievance)
        if secretariat_id:
            query = query.where(Grievance.secretariat_id == secretariat_id)
        if status:
            query = query.where(Grievance.status == status)
        if start_date:
            query = query.where(Grievance.created_at >= start_date)
        if end_date:
            query = query.where(Grievance.created_at <= end_date)
        query = query.order_by(Grievance.created_at.desc()).limit(5000)

        result = await self.db.execute(query)
        grievances = result.scalars().all()

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow([
            "Reference Number", "Citizen Name", "Category", "Department",
            "Subject", "Status", "Priority", "Escalation Level",
            "SLA Deadline", "SLA Breached", "Filed Date", "Resolved Date",
            "Resolution Notes",
        ])
        for g in grievances:
            writer.writerow([
                g.reference_number, g.citizen_name, g.category, g.department,
                g.subject_te, g.status, g.priority, g.escalation_level,
                g.sla_deadline.isoformat() if g.sla_deadline else "",
                g.is_sla_breached, g.created_at.isoformat(),
                g.resolved_at.isoformat() if g.resolved_at else "",
                g.resolution_notes_te or "",
            ])
        return output.getvalue()

    async def export_tasks_csv(
        self,
        employee_id: int | None = None,
        status: str | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> str:
        """Export tasks as CSV string."""
        query = select(Task)
        if employee_id:
            query = query.where(Task.employee_id == employee_id)
        if status:
            query = query.where(Task.status == status)
        if start_date:
            query = query.where(Task.created_at >= start_date)
        if end_date:
            query = query.where(Task.created_at <= end_date)
        query = query.order_by(Task.created_at.desc()).limit(5000)

        result = await self.db.execute(query)
        tasks = result.scalars().all()

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow([
            "Task ID", "Title (Telugu)", "Department", "Category",
            "Priority", "Score", "Due Date", "Status",
            "Estimated Min", "Actual Min", "Source", "Created", "Completed",
        ])
        for t in tasks:
            writer.writerow([
                str(t.id), t.title_te, t.department, t.category,
                t.priority, t.priority_score, t.due_date or "",
                t.status, t.estimated_minutes, t.actual_minutes or "",
                t.source, t.created_at.isoformat(),
                t.completed_at.isoformat() if t.completed_at else "",
            ])
        return output.getvalue()
