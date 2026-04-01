"""
Smart Notification Service — Proactive SLA warnings, task deadline alerts,
scheme updates, and daily summaries via WhatsApp.
"""
from datetime import datetime, timedelta, timezone

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.grievance import Grievance
from app.models.task import Task
from app.models.user import Employee
from app.services.whatsapp_service import WhatsAppService

logger = structlog.get_logger()

# Send SLA warning 12 hours before deadline
SLA_WARNING_HOURS = 12


class NotificationService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.wa = WhatsAppService()

    async def check_sla_warnings(self) -> int:
        """Find grievances within 12 hours of SLA deadline and send warnings."""
        now = datetime.now(timezone.utc)
        warning_cutoff = now + timedelta(hours=SLA_WARNING_HOURS)

        result = await self.db.execute(
            select(Grievance, Employee)
            .join(Employee, Grievance.filed_by_employee_id == Employee.id)
            .where(Grievance.status.in_(["open", "acknowledged", "in_progress"]))
            .where(Grievance.sla_deadline <= warning_cutoff)
            .where(Grievance.sla_deadline > now)
            .where(Grievance.is_sla_breached.is_(False))
        )
        rows = result.all()

        sent = 0
        for grievance, employee in rows:
            hours_left = (grievance.sla_deadline - now).total_seconds() / 3600
            try:
                await self.wa.send_text(
                    employee.phone_number,
                    f"⚠️ SLA Warning — {grievance.reference_number}\n\n"
                    f"ఫిర్యాదు deadline {int(hours_left)} గంటల్లో ఉంది!\n"
                    f"Category: {grievance.category}\n"
                    f"Subject: {grievance.subject_te[:100]}\n\n"
                    f"దయచేసి వెంటనే పరిష్కరించండి.",
                )
                sent += 1
            except Exception as e:
                logger.error("SLA warning send failed", ref=grievance.reference_number, error=str(e))

        logger.info("SLA warnings sent", count=sent)
        return sent

    async def check_task_deadlines(self) -> int:
        """Find tasks due today that haven't been started and notify."""
        from datetime import date
        today = date.today()

        result = await self.db.execute(
            select(Task, Employee)
            .join(Employee, Task.employee_id == Employee.id)
            .where(Task.due_date == today)
            .where(Task.status == "pending")
        )
        rows = result.all()

        sent = 0
        for task, employee in rows:
            try:
                await self.wa.send_text(
                    employee.phone_number,
                    f"⏰ Task Due Today\n\n"
                    f"📋 {task.title_te}\n"
                    f"🏢 {task.department}\n"
                    f"⏱️ ~{task.estimated_minutes} min\n\n"
                    f"'task' అని reply చేసి daily plan చూడండి.",
                )
                sent += 1
            except Exception as e:
                logger.error("Task deadline notify failed", task_id=str(task.id), error=str(e))

        logger.info("Task deadline notifications sent", count=sent)
        return sent

    async def notify_grievance_status_change(
        self, reference_number: str, old_status: str, new_status: str, employee_phone: str
    ):
        """Send WhatsApp notification on grievance status change."""
        status_icons = {
            "acknowledged": "🔵",
            "in_progress": "🔄",
            "escalated": "🟠",
            "resolved": "✅",
            "closed": "⬛",
        }
        icon = status_icons.get(new_status, "📋")

        await self.wa.send_text(
            employee_phone,
            f"{icon} ఫిర్యాదు Update — {reference_number}\n\n"
            f"Status: {old_status} → {new_status}\n\n"
            f"Details కోసం '{reference_number}' అని reply చేయండి.",
        )

    async def send_daily_summary(self, employee_id: int) -> bool:
        """Send daily summary: pending tasks, open grievances, deadlines."""
        from datetime import date
        from sqlalchemy import func
        today = date.today()

        emp_result = await self.db.execute(
            select(Employee).where(Employee.id == employee_id)
        )
        employee = emp_result.scalar_one_or_none()
        if not employee:
            return False

        # Count pending tasks
        pending_tasks = (await self.db.execute(
            select(func.count()).where(
                Task.employee_id == employee_id,
                Task.status.in_(["pending", "in_progress"]),
            )
        )).scalar() or 0

        # Count overdue tasks
        overdue_tasks = (await self.db.execute(
            select(func.count()).where(
                Task.employee_id == employee_id,
                Task.status == "pending",
                Task.due_date < today,
            )
        )).scalar() or 0

        # Count open grievances
        open_grievances = (await self.db.execute(
            select(func.count()).where(
                Grievance.filed_by_employee_id == employee_id,
                Grievance.status.in_(["open", "acknowledged", "in_progress"]),
            )
        )).scalar() or 0

        name = employee.name_te if employee.name_te != "Unknown" else employee.name_en or ""

        msg = (
            f"🌅 శుభోదయం {name} గారు!\n\n"
            f"📊 Daily Summary — {today.strftime('%d/%m/%Y')}\n\n"
            f"📋 Pending Tasks: {pending_tasks}\n"
        )
        if overdue_tasks:
            msg += f"🔴 Overdue Tasks: {overdue_tasks}\n"
        msg += f"📋 Open Grievances: {open_grievances}\n\n"
        msg += "'task' అని reply చేసి daily plan చూడండి."

        try:
            await self.wa.send_text(employee.phone_number, msg)
            return True
        except Exception as e:
            logger.error("Daily summary failed", employee_id=employee_id, error=str(e))
            return False
