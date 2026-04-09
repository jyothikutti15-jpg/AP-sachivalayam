"""
Citizen Follow-up Reminders — Auto-schedule WhatsApp reminders for
pending documents, renewal deadlines, and payment disbursement dates.

Extends the existing Celery beat + WhatsApp notification infrastructure.
"""

import uuid
from datetime import date, datetime, timedelta, timezone

import structlog
from sqlalchemy import select, func, and_, case
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.reminder import CitizenReminder
from app.models.scheme import Scheme
from app.schemas.reminder import (
    AutoReminderRequest,
    ReminderCreate,
    ReminderResponse,
    ReminderStatsResponse,
    ReminderUpdate,
)
from app.core.language_config import (
    REMINDER_TEMPLATES_I18N,
    get_document_name,
    get_reminder_template,
)

logger = structlog.get_logger()

# Backward-compatible: REMINDER_TEMPLATES defaults to Telugu
REMINDER_TEMPLATES = REMINDER_TEMPLATES_I18N["te"]


class ReminderService:
    """Manages citizen follow-up reminders."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_reminder(self, data: ReminderCreate) -> CitizenReminder:
        """Create a new citizen reminder."""
        # Look up scheme name if scheme_code provided
        scheme_name_te = None
        if data.scheme_code:
            result = await self.db.execute(
                select(Scheme.name_te).where(Scheme.scheme_code == data.scheme_code)
            )
            scheme_name_te = result.scalar_one_or_none()

        reminder = CitizenReminder(
            employee_id=data.employee_id,
            secretariat_id=data.secretariat_id,
            citizen_name=data.citizen_name,
            citizen_phone=data.citizen_phone,
            reminder_type=data.reminder_type,
            scheme_code=data.scheme_code,
            scheme_name_te=scheme_name_te,
            message_te=data.message_te,
            message_en=data.message_en,
            pending_items=data.pending_items,
            reminder_date=data.reminder_date,
            reminder_time=data.reminder_time,
            is_recurring=data.is_recurring,
            recurrence_rule=data.recurrence_rule,
            recurrence_end_date=data.recurrence_end_date,
            priority=data.priority,
            form_submission_id=data.form_submission_id,
            grievance_reference=data.grievance_reference,
        )
        self.db.add(reminder)
        await self.db.flush()
        await self.db.refresh(reminder)

        logger.info(
            "Reminder created",
            reminder_id=str(reminder.id),
            citizen=data.citizen_name,
            type=data.reminder_type,
            date=str(data.reminder_date),
        )
        return reminder

    async def auto_generate_reminders(
        self, request: AutoReminderRequest
    ) -> list[CitizenReminder]:
        """Auto-generate reminders from a scheme application with missing documents."""
        # Look up scheme name
        result = await self.db.execute(
            select(Scheme).where(Scheme.scheme_code == request.scheme_code)
        )
        scheme = result.scalar_one_or_none()
        scheme_name = scheme.name_te if scheme else request.scheme_code

        reminders = []
        deadline = request.deadline or (date.today() + timedelta(days=15))

        if request.missing_documents:
            # Build document names in citizen's language
            lang = getattr(request, "language", None) or "te"
            doc_names = []
            for doc in request.missing_documents:
                doc_names.append(get_document_name(doc, lang))

            message = get_reminder_template(lang, "pending_documents").format(
                citizen_name=request.citizen_name,
                scheme_name=scheme_name,
                documents=", ".join(doc_names),
                deadline=deadline.strftime("%d-%m-%Y"),
            )

            # First reminder: 3 days from now
            r1 = await self.create_reminder(ReminderCreate(
                employee_id=request.employee_id,
                secretariat_id=request.secretariat_id,
                citizen_name=request.citizen_name,
                citizen_phone=request.citizen_phone,
                reminder_type="pending_documents",
                scheme_code=request.scheme_code,
                message_te=message,
                pending_items=request.missing_documents,
                reminder_date=date.today() + timedelta(days=3),
                priority="high",
            ))
            reminders.append(r1)

            # Second reminder: 3 days before deadline
            if deadline > date.today() + timedelta(days=6):
                r2 = await self.create_reminder(ReminderCreate(
                    employee_id=request.employee_id,
                    secretariat_id=request.secretariat_id,
                    citizen_name=request.citizen_name,
                    citizen_phone=request.citizen_phone,
                    reminder_type="pending_documents",
                    scheme_code=request.scheme_code,
                    message_te=message,
                    pending_items=request.missing_documents,
                    reminder_date=deadline - timedelta(days=3),
                    priority="urgent",
                ))
                reminders.append(r2)

        logger.info(
            "Auto-generated reminders",
            citizen=request.citizen_name,
            scheme=request.scheme_code,
            count=len(reminders),
        )
        return reminders

    async def list_reminders(
        self,
        employee_id: int | None = None,
        status: str | None = None,
        reminder_type: str | None = None,
        from_date: date | None = None,
        to_date: date | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[CitizenReminder]:
        """List reminders with filters."""
        query = select(CitizenReminder).order_by(CitizenReminder.reminder_date)

        if employee_id:
            query = query.where(CitizenReminder.employee_id == employee_id)
        if status:
            query = query.where(CitizenReminder.status == status)
        if reminder_type:
            query = query.where(CitizenReminder.reminder_type == reminder_type)
        if from_date:
            query = query.where(CitizenReminder.reminder_date >= from_date)
        if to_date:
            query = query.where(CitizenReminder.reminder_date <= to_date)

        query = query.offset(offset).limit(limit)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def update_reminder(
        self, reminder_id: str, update: ReminderUpdate
    ) -> CitizenReminder | None:
        """Update a reminder's status or details."""
        result = await self.db.execute(
            select(CitizenReminder).where(CitizenReminder.id == uuid.UUID(reminder_id))
        )
        reminder = result.scalar_one_or_none()
        if not reminder:
            return None

        if update.status:
            reminder.status = update.status
            if update.status == "acknowledged":
                reminder.acknowledged_at = datetime.now(tz=timezone.utc)
        if update.message_te:
            reminder.message_te = update.message_te
        if update.reminder_date:
            reminder.reminder_date = update.reminder_date
        if update.reminder_time:
            reminder.reminder_time = update.reminder_time
        if update.priority:
            reminder.priority = update.priority

        return reminder

    async def get_due_reminders(self, target_date: date | None = None) -> list[CitizenReminder]:
        """Get all reminders due for sending on a given date."""
        target = target_date or date.today()
        result = await self.db.execute(
            select(CitizenReminder).where(
                and_(
                    CitizenReminder.reminder_date == target,
                    CitizenReminder.status == "scheduled",
                    CitizenReminder.send_count < CitizenReminder.max_sends,
                )
            ).order_by(
                case(
                    (CitizenReminder.priority == "urgent", 0),
                    (CitizenReminder.priority == "high", 1),
                    (CitizenReminder.priority == "medium", 2),
                    else_=3,
                )
            )
        )
        return list(result.scalars().all())

    async def mark_sent(self, reminder_id: str) -> None:
        """Mark a reminder as sent."""
        result = await self.db.execute(
            select(CitizenReminder).where(CitizenReminder.id == uuid.UUID(reminder_id))
        )
        reminder = result.scalar_one_or_none()
        if reminder:
            reminder.status = "sent"
            reminder.sent_at = datetime.now(tz=timezone.utc)
            reminder.send_count += 1

            # Schedule next occurrence for recurring reminders
            if reminder.is_recurring and reminder.recurrence_rule:
                await self._schedule_next(reminder)

    async def _schedule_next(self, reminder: CitizenReminder) -> None:
        """Schedule the next occurrence of a recurring reminder."""
        next_date = None
        if reminder.recurrence_rule == "daily":
            next_date = reminder.reminder_date + timedelta(days=1)
        elif reminder.recurrence_rule == "weekly":
            next_date = reminder.reminder_date + timedelta(weeks=1)
        elif reminder.recurrence_rule == "monthly":
            next_date = reminder.reminder_date + timedelta(days=30)

        if not next_date:
            return

        # Don't schedule past the end date
        if reminder.recurrence_end_date and next_date > reminder.recurrence_end_date:
            return

        next_reminder = CitizenReminder(
            employee_id=reminder.employee_id,
            secretariat_id=reminder.secretariat_id,
            citizen_name=reminder.citizen_name,
            citizen_phone=reminder.citizen_phone,
            reminder_type=reminder.reminder_type,
            scheme_code=reminder.scheme_code,
            scheme_name_te=reminder.scheme_name_te,
            message_te=reminder.message_te,
            message_en=reminder.message_en,
            pending_items=reminder.pending_items,
            reminder_date=next_date,
            reminder_time=reminder.reminder_time,
            is_recurring=True,
            recurrence_rule=reminder.recurrence_rule,
            recurrence_end_date=reminder.recurrence_end_date,
            priority=reminder.priority,
            max_sends=reminder.max_sends,
        )
        self.db.add(next_reminder)

    async def get_stats(
        self, employee_id: int | None = None
    ) -> ReminderStatsResponse:
        """Get reminder statistics."""
        base_query = select(
            CitizenReminder.status,
            func.count(CitizenReminder.id).label("count"),
        ).group_by(CitizenReminder.status)

        if employee_id:
            base_query = base_query.where(
                CitizenReminder.employee_id == employee_id
            )

        result = await self.db.execute(base_query)
        status_counts = {row.status: row.count for row in result.all()}

        # By type
        type_query = select(
            CitizenReminder.reminder_type,
            func.count(CitizenReminder.id).label("count"),
        ).group_by(CitizenReminder.reminder_type)
        if employee_id:
            type_query = type_query.where(
                CitizenReminder.employee_id == employee_id
            )
        type_result = await self.db.execute(type_query)
        type_counts = {row.reminder_type: row.count for row in type_result.all()}

        return ReminderStatsResponse(
            total_scheduled=status_counts.get("scheduled", 0),
            total_sent=status_counts.get("sent", 0),
            total_acknowledged=status_counts.get("acknowledged", 0),
            total_completed=status_counts.get("completed", 0),
            total_failed=status_counts.get("failed", 0),
            total_cancelled=status_counts.get("cancelled", 0),
            by_type=type_counts,
        )
