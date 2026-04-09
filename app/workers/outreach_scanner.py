"""
Outreach scanner worker — Scans all secretariats for eligible beneficiaries
who haven't applied for schemes they qualify for. Runs weekly via Celery beat.
"""
import structlog

from app.workers.celery_app import celery_app as celery

logger = structlog.get_logger()


@celery.task(
    name="scan_outreach",
    autoretry_for=(Exception,),
    max_retries=2,
    retry_backoff=60,
    retry_backoff_max=3600,
    retry_jitter=True,
)
def scan_outreach():
    """Scan all secretariats for outreach opportunities."""
    import asyncio

    async def _run():
        from sqlalchemy import select

        from app.dependencies import AsyncSessionLocal
        from app.models.user import Secretariat
        from app.services.outreach_engine import OutreachEngine

        total_matches = 0
        secretariats_scanned = 0

        async with AsyncSessionLocal() as db:
            result = await db.execute(select(Secretariat.id))
            secretariat_ids = [row[0] for row in result.all()]

            for sec_id in secretariat_ids:
                try:
                    engine = OutreachEngine(db=db)
                    matches = await engine.scan_secretariat(sec_id)
                    total_matches += len(matches)
                    secretariats_scanned += 1
                except Exception as exc:
                    logger.error("Outreach scan failed for secretariat",
                                 secretariat_id=sec_id, error=str(exc))

            await db.commit()

        logger.info(
            "Weekly outreach scan complete",
            secretariats_scanned=secretariats_scanned,
            total_matches=total_matches,
        )
        return {"secretariats_scanned": secretariats_scanned, "total_matches": total_matches}

    return asyncio.get_event_loop().run_until_complete(_run())
