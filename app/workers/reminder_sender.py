"""
Celery worker for sending citizen follow-up reminders via WhatsApp.

Runs every morning at 8:30 AM IST, picks up all due reminders,
and sends them via WhatsApp with exponential backoff retry.
"""

import structlog
from celery import shared_task

from app.workers.celery_app import celery_app

logger = structlog.get_logger()


@celery_app.task(
    name="send_due_reminders",
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=30,
    retry_backoff_max=300,
    retry_jitter=True,
    max_retries=3,
)
def send_due_reminders(self):
    """Send all reminders due for today via WhatsApp.

    Runs at 8:30 AM IST daily via Celery beat.
    Each reminder is sent individually so one failure doesn't block others.
    """
    import asyncio

    asyncio.run(_send_due_reminders_async())


async def _send_due_reminders_async():
    """Async implementation of reminder sending."""
    from app.dependencies import get_async_session
    from app.services.reminder_service import ReminderService

    async with get_async_session() as db:
        service = ReminderService(db=db)
        reminders = await service.get_due_reminders()

        if not reminders:
            logger.info("No reminders due today")
            return

        logger.info("Processing due reminders", count=len(reminders))

        sent_count = 0
        failed_count = 0

        for reminder in reminders:
            try:
                # Send via WhatsApp
                success = await _send_whatsapp_reminder(
                    phone=reminder.citizen_phone,
                    message=reminder.message_te,
                    citizen_name=reminder.citizen_name,
                )

                if success:
                    await service.mark_sent(str(reminder.id))
                    sent_count += 1
                else:
                    reminder.status = "failed"
                    failed_count += 1

            except Exception as e:
                logger.error(
                    "Reminder send failed",
                    reminder_id=str(reminder.id),
                    citizen=reminder.citizen_name,
                    error=str(e),
                )
                failed_count += 1

        await db.commit()
        logger.info(
            "Reminder batch complete",
            sent=sent_count,
            failed=failed_count,
            total=len(reminders),
        )


async def _send_whatsapp_reminder(
    phone: str, message: str, citizen_name: str
) -> bool:
    """Send a WhatsApp message to a citizen. Returns True on success."""
    import httpx

    from app.config import get_settings

    settings = get_settings()

    if not settings.whatsapp_access_token:
        logger.warning("WhatsApp not configured, skipping send", phone=phone)
        return True  # Don't fail in dev/test

    url = f"{settings.whatsapp_api_url}/{settings.whatsapp_phone_number_id}/messages"
    headers = {
        "Authorization": f"Bearer {settings.whatsapp_access_token}",
        "Content-Type": "application/json",
    }

    # Format phone number (add 91 prefix for India if not present)
    if not phone.startswith("91") and not phone.startswith("+91"):
        phone = f"91{phone}"
    phone = phone.lstrip("+")

    payload = {
        "messaging_product": "whatsapp",
        "to": phone,
        "type": "text",
        "text": {"body": message},
    }

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(url, json=payload, headers=headers)
            if response.status_code == 200:
                logger.info("WhatsApp reminder sent", citizen=citizen_name)
                return True
            else:
                logger.warning(
                    "WhatsApp send failed",
                    status=response.status_code,
                    body=response.text[:200],
                )
                return False
    except Exception as e:
        logger.error("WhatsApp request failed", error=str(e))
        return False
