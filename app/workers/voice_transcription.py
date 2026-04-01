import asyncio

import structlog

from app.workers.celery_app import celery_app

logger = structlog.get_logger()


@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
def transcribe_voice_note(self, media_id: str, phone_number: str, session_id: str):
    """Async task to transcribe a WhatsApp voice note."""
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    return loop.run_until_complete(
        _transcribe_and_respond(media_id, phone_number, session_id)
    )


async def _transcribe_and_respond(media_id: str, phone_number: str, session_id: str):
    """Download voice note, transcribe, and send back to conversation engine."""
    from app.services.voice_pipeline import VoicePipeline
    from app.services.whatsapp_service import WhatsAppService

    wa = WhatsAppService()
    pipeline = VoicePipeline()

    try:
        # Download voice note from WhatsApp CDN
        audio_data = await wa.download_media(media_id)

        # Transcribe
        result = await pipeline.transcribe(audio_data, language="te")

        logger.info(
            "Voice transcription complete",
            phone=phone_number[-4:],
            text_preview=result.text[:50],
            confidence=result.confidence,
        )

        return {
            "text": result.text,
            "language": result.language,
            "confidence": result.confidence,
            "entities": result.entities,
        }

    except Exception as exc:
        logger.error("Voice transcription failed", error=str(exc))
        # Notify employee of failure
        await wa.send_text(
            phone_number,
            "క్షమించండి, voice note process చేయడంలో సమస్య. దయచేసి text లో పంపండి.",
        )
        raise


@celery_app.task
def process_offline_queue():
    """Process pending offline queue items."""
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    return loop.run_until_complete(_process_queue())


async def _process_queue():
    from app.dependencies import async_session_factory
    from app.services.offline_queue import OfflineQueueService

    async with async_session_factory() as session:
        service = OfflineQueueService(db=session)
        processed = await service.process_pending()
        await session.commit()
        logger.info("Offline queue processed", count=processed)
        return processed
