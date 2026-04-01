import asyncio

import structlog

from app.workers.celery_app import celery_app

logger = structlog.get_logger()


@celery_app.task
def sync_gsws_data():
    """Nightly sync of scheme data from GSWS portal."""
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    return loop.run_until_complete(_sync())


async def _sync():
    from app.dependencies import async_session_factory
    from app.services.gsws_bridge import GSWSBridge

    async with async_session_factory() as session:
        bridge = GSWSBridge(db=session)
        try:
            result = await bridge.sync_scheme_data()
            await session.commit()
            logger.info("GSWS sync complete", result=result)
            return result
        except Exception as e:
            logger.error("GSWS sync failed", error=str(e))
            return {"status": "failed", "error": str(e)}


@celery_app.task
def aggregate_daily_metrics():
    """Aggregate daily usage metrics for analytics dashboard."""
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    return loop.run_until_complete(_aggregate())


async def _aggregate():
    from datetime import date, datetime, timezone

    from sqlalchemy import func, select

    from app.dependencies import async_session_factory
    from app.models.analytics import DailyMetric
    from app.models.form import FormSubmission
    from app.models.interaction import ChatSession, Message

    today = date.today()

    async with async_session_factory() as session:
        # Get all employees who had sessions today
        result = await session.execute(
            select(ChatSession.employee_id)
            .where(func.date(ChatSession.started_at) == today)
            .distinct()
        )
        employee_ids = [row[0] for row in result.all()]

        for emp_id in employee_ids:
            # Count messages
            msg_count_result = await session.execute(
                select(func.count(Message.id))
                .join(ChatSession)
                .where(ChatSession.employee_id == emp_id)
                .where(func.date(ChatSession.started_at) == today)
                .where(Message.direction == "in")
            )
            queries = msg_count_result.scalar() or 0

            # Count forms filled
            form_count_result = await session.execute(
                select(func.count(FormSubmission.id))
                .where(FormSubmission.employee_id == emp_id)
                .where(func.date(FormSubmission.created_at) == today)
            )
            forms = form_count_result.scalar() or 0

            # Avg response time
            avg_rt_result = await session.execute(
                select(func.avg(Message.response_time_ms))
                .join(ChatSession)
                .where(ChatSession.employee_id == emp_id)
                .where(func.date(ChatSession.started_at) == today)
                .where(Message.direction == "out")
                .where(Message.response_time_ms.isnot(None))
            )
            avg_rt = avg_rt_result.scalar()

            # Estimate time saved
            time_saved = queries * 15 + forms * 30  # minutes

            # Upsert daily metric
            from sqlalchemy.dialects.postgresql import insert

            stmt = insert(DailyMetric).values(
                employee_id=emp_id,
                date=today,
                queries_handled=queries,
                forms_auto_filled=forms,
                time_saved_minutes=time_saved,
                session_count=1,
                avg_response_time_ms=int(avg_rt) if avg_rt else None,
            ).on_conflict_do_update(
                index_elements=["employee_id", "date"],
                set_={
                    "queries_handled": queries,
                    "forms_auto_filled": forms,
                    "time_saved_minutes": time_saved,
                    "avg_response_time_ms": int(avg_rt) if avg_rt else None,
                },
            )
            await session.execute(stmt)

        await session.commit()
        logger.info("Daily metrics aggregated", employees=len(employee_ids), date=str(today))
        return {"employees_processed": len(employee_ids)}
