"""
Task scheduler worker — Generates daily task plans for all active employees
at 6 AM IST. Sends prioritized task list via WhatsApp.
"""
import structlog

from app.workers.celery_app import celery_app as celery

logger = structlog.get_logger()


@celery.task(name="generate_daily_plans")
def generate_daily_plans():
    """Generate AI-powered daily plans for all active employees. Runs 6 AM IST."""
    import asyncio

    async def _run():
        from sqlalchemy import select

        from app.dependencies import AsyncSessionLocal
        from app.models.user import Employee
        from app.services.task_service import TaskService
        from app.services.whatsapp_service import WhatsAppService

        async with AsyncSessionLocal() as db:
            # Get all active employees
            result = await db.execute(
                select(Employee).where(Employee.is_active.is_(True))
            )
            employees = result.scalars().all()

            wa = WhatsAppService()
            generated = 0

            for employee in employees:
                try:
                    service = TaskService(db=db)
                    plan = await service.generate_daily_plan(employee.id)

                    if plan.tasks:
                        # Send via WhatsApp
                        msg = _format_daily_plan_message(plan, employee)
                        await wa.send_text(employee.phone_number, msg)
                        generated += 1

                except Exception as e:
                    logger.error(
                        "Daily plan generation failed",
                        employee_id=employee.id,
                        error=str(e),
                    )

            await db.commit()
            logger.info("Daily plans generated", total=generated)
            return generated

    return asyncio.get_event_loop().run_until_complete(_run())


def _format_daily_plan_message(plan, employee) -> str:
    """Format daily plan as WhatsApp message."""
    name = employee.name_te if employee.name_te != "Unknown" else employee.name_en or ""

    lines = [
        f"🌅 శుభోదయం {name} గారు!",
        f"📋 ఈ రోజు Task Plan — {plan.plan_date.strftime('%d/%m/%Y')}",
        "",
    ]

    if plan.ai_summary_te:
        lines.append(plan.ai_summary_te)
        lines.append("")

    for task in plan.tasks[:10]:  # Max 10 tasks in WhatsApp message
        status_icon = {
            "pending": "⬜",
            "in_progress": "🔄",
            "overdue": "🔴",
        }.get(task.status, "⬜")

        priority_icon = {
            "urgent": "🔴",
            "high": "🟠",
            "medium": "🟡",
            "low": "🟢",
        }.get(task.priority, "⬜")

        lines.append(
            f"{task.rank}. {status_icon} {task.title_te}\n"
            f"   {priority_icon} {task.department} • ~{task.estimated_minutes} min"
        )
        if task.reason_te:
            lines.append(f"   💡 {task.reason_te}")
        lines.append("")

    lines.append(f"⏱️ Total: ~{plan.total_estimated_minutes} minutes")
    lines.append("\n'task done' అని reply చేసి task complete చేయండి.")

    return "\n".join(lines)


@celery.task(name="create_recurring_tasks")
def create_recurring_tasks():
    """Create recurring tasks for the day. Runs 5:30 AM IST."""
    import asyncio
    from datetime import date

    async def _run():
        from sqlalchemy import select

        from app.dependencies import AsyncSessionLocal
        from app.models.task import Task
        from app.services.task_service import TaskService

        today = date.today()
        weekday = today.strftime("%A").lower()

        async with AsyncSessionLocal() as db:
            # Find recurring task templates
            result = await db.execute(
                select(Task).where(
                    Task.is_recurring.is_(True),
                    Task.status.in_(["completed", "pending"]),
                )
            )
            templates = result.scalars().all()

            created = 0
            service = TaskService(db=db)

            for template in templates:
                if not _should_create_today(template.recurrence_rule, today, weekday):
                    continue

                # Check if already created today
                existing = await db.execute(
                    select(Task).where(
                        Task.employee_id == template.employee_id,
                        Task.title_te == template.title_te,
                        Task.due_date == today,
                        Task.source == "recurring",
                    )
                )
                if existing.scalar_one_or_none():
                    continue

                from app.schemas.task import TaskCreateRequest

                await service.create_task(
                    TaskCreateRequest(
                        title_te=template.title_te,
                        title_en=template.title_en,
                        description_te=template.description_te,
                        department=template.department,
                        category=template.category,
                        priority=template.priority,
                        due_date=today,
                        estimated_minutes=template.estimated_minutes,
                        source="recurring",
                        source_reference_id=str(template.id),
                    ),
                    employee_id=template.employee_id,
                    secretariat_id=template.secretariat_id,
                )
                created += 1

            await db.commit()
            logger.info("Recurring tasks created", count=created)
            return created

    return asyncio.get_event_loop().run_until_complete(_run())


def _should_create_today(rule: str | None, today, weekday: str) -> bool:
    """Check if a recurring task should be created today."""
    if not rule:
        return False
    rule = rule.lower()
    if rule == "daily":
        return True
    if rule == "weekly" and weekday == "monday":
        return True
    if rule == "monthly" and today.day == 1:
        return True
    if rule == f"every_{weekday}":
        return True
    if rule == "weekdays" and weekday not in ("saturday", "sunday"):
        return True
    return False
