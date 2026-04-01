"""
Grievance escalation worker — Checks for SLA-breached grievances
and auto-escalates them. Runs every 30 minutes via Celery beat.
"""
import structlog

from app.workers.celery_app import celery_app as celery

logger = structlog.get_logger()


@celery.task(name="check_grievance_sla")
def check_grievance_sla():
    """Check for overdue grievances and auto-escalate."""
    import asyncio

    async def _run():
        from app.dependencies import AsyncSessionLocal
        from app.services.grievance_service import GrievanceService

        async with AsyncSessionLocal() as db:
            service = GrievanceService(db=db)
            escalated = await service.check_and_escalate_overdue()
            await db.commit()
            logger.info("Grievance SLA check completed", escalated=escalated)
            return escalated

    return asyncio.get_event_loop().run_until_complete(_run())


@celery.task(name="send_grievance_notification")
def send_grievance_notification(
    phone_number: str,
    reference_number: str,
    status: str,
    message_te: str,
):
    """Send grievance status update via WhatsApp."""
    import asyncio

    async def _run():
        from app.services.whatsapp_service import WhatsAppService

        wa = WhatsAppService()
        text = (
            f"📋 ఫిర్యాదు Update — {reference_number}\n\n"
            f"Status: {status}\n"
            f"{message_te}"
        )
        await wa.send_text(phone_number, text)
        logger.info("Grievance notification sent", reference=reference_number)

    return asyncio.get_event_loop().run_until_complete(_run())
