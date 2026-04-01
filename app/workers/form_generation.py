"""Celery task for async PDF form generation."""
import asyncio

import structlog

from app.workers.celery_app import celery_app

logger = structlog.get_logger()


@celery_app.task(bind=True, max_retries=2, default_retry_delay=30)
def generate_form_pdf(self, submission_id: str):
    """Generate a PDF form from a submission (async Celery task)."""
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    return loop.run_until_complete(_generate_pdf(submission_id))


async def _generate_pdf(submission_id: str) -> dict:
    """Generate PDF using the PDFGenerator service."""
    from uuid import UUID

    from app.dependencies import async_session_factory
    from app.services.pdf_generator import PDFGenerator

    async with async_session_factory() as session:
        generator = PDFGenerator(db=session)
        pdf_path = await generator.generate(UUID(submission_id))
        await session.commit()

        if pdf_path:
            logger.info("PDF generated via Celery", submission_id=submission_id, path=pdf_path)
            return {"status": "success", "pdf_path": pdf_path}
        else:
            logger.error("PDF generation failed", submission_id=submission_id)
            return {"status": "error", "message": "PDF generation failed"}


@celery_app.task
def generate_and_send_pdf(submission_id: str, phone_number: str):
    """Generate PDF and send it via WhatsApp."""
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    return loop.run_until_complete(_generate_and_send(submission_id, phone_number))


async def _generate_and_send(submission_id: str, phone_number: str) -> dict:
    """Generate PDF and send via WhatsApp."""
    from uuid import UUID

    from app.dependencies import async_session_factory
    from app.services.pdf_generator import PDFGenerator
    from app.services.whatsapp_service import WhatsAppService

    async with async_session_factory() as session:
        generator = PDFGenerator(db=session)
        pdf_path = await generator.generate(UUID(submission_id))
        await session.commit()

    if pdf_path:
        wa = WhatsAppService()
        try:
            await wa.send_document(
                to=phone_number,
                document_url=pdf_path,
                caption="📄 మీ form PDF ready. దయచేసి verify చేసి GSWS portal లో submit చేయండి.",
                filename=f"form_{submission_id[:8]}.pdf",
            )
            return {"status": "sent", "pdf_path": pdf_path}
        except Exception as e:
            logger.error("WhatsApp PDF send failed", error=str(e))
            await wa.send_text(
                phone_number,
                "📄 PDF generate అయింది కానీ send చేయడంలో సమస్య. దయచేసి మళ్ళీ ప్రయత్నించండి."
            )
            return {"status": "generated_not_sent", "pdf_path": pdf_path}
    else:
        return {"status": "error"}
