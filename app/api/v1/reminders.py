"""
API endpoints for Citizen Follow-up Reminders (Feature 10).

Employees can schedule WhatsApp reminders for citizens about pending
documents, renewal deadlines, and disbursement dates.
"""

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db
from app.schemas.reminder import (
    AutoReminderRequest,
    ReminderCreate,
    ReminderResponse,
    ReminderStatsResponse,
    ReminderUpdate,
)
from app.services.reminder_service import ReminderService

router = APIRouter()


@router.post("/", response_model=ReminderResponse, status_code=201)
async def create_reminder(
    data: ReminderCreate,
    db: AsyncSession = Depends(get_db),
):
    """Schedule a follow-up reminder for a citizen."""
    service = ReminderService(db=db)
    reminder = await service.create_reminder(data)
    await db.commit()
    return reminder


@router.post("/auto-generate", response_model=list[ReminderResponse])
async def auto_generate_reminders(
    request: AutoReminderRequest,
    db: AsyncSession = Depends(get_db),
):
    """Auto-generate reminders from a scheme application.

    Given a scheme code and list of missing documents, automatically
    creates appropriately timed reminders (3 days from now + 3 days
    before deadline) with Telugu messages.
    """
    service = ReminderService(db=db)
    reminders = await service.auto_generate_reminders(request)
    await db.commit()
    return reminders


@router.get("/", response_model=list[ReminderResponse])
async def list_reminders(
    employee_id: int | None = None,
    status: str | None = None,
    reminder_type: str | None = None,
    from_date: date | None = None,
    to_date: date | None = None,
    limit: int = Query(default=50, le=200),
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
):
    """List reminders with filters."""
    service = ReminderService(db=db)
    return await service.list_reminders(
        employee_id=employee_id,
        status=status,
        reminder_type=reminder_type,
        from_date=from_date,
        to_date=to_date,
        limit=limit,
        offset=offset,
    )


@router.patch("/{reminder_id}", response_model=ReminderResponse)
async def update_reminder(
    reminder_id: str,
    update: ReminderUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Update a reminder's status or details."""
    service = ReminderService(db=db)
    reminder = await service.update_reminder(reminder_id, update)
    if not reminder:
        raise HTTPException(status_code=404, detail="Reminder not found")
    await db.commit()
    return reminder


@router.get("/stats", response_model=ReminderStatsResponse)
async def get_reminder_stats(
    employee_id: int | None = None,
    db: AsyncSession = Depends(get_db),
):
    """Get reminder statistics (total by status, type, scheme)."""
    service = ReminderService(db=db)
    return await service.get_stats(employee_id=employee_id)


@router.get("/due-today", response_model=list[ReminderResponse])
async def get_due_today(
    db: AsyncSession = Depends(get_db),
):
    """Get all reminders due for sending today."""
    service = ReminderService(db=db)
    return await service.get_due_reminders()
