"""
Offline Queue — Manages operations for low-connectivity scenarios.

Three-tier offline strategy:
1. Redis FAQ cache (zero connectivity) — pre-warmed top 200 FAQs
2. Offline queue (intermittent) — failed ops retried every 5 min with exponential backoff
3. Keyword fallback (no LLM) — scheme lookup from local PostgreSQL
"""
from datetime import datetime, timezone

import structlog
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.offline import OfflineQueueItem
from app.models.scheme import Scheme

logger = structlog.get_logger()

MAX_RETRIES = 5
# Exponential backoff: retry after 5min, 10min, 20min, 40min, 80min
BASE_RETRY_SECONDS = 300


class OfflineQueueService:
    """Manages offline queue for low-connectivity scenarios."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def enqueue(
        self, employee_id: int, action_type: str, payload: dict
    ) -> OfflineQueueItem:
        """Add an operation to the offline queue."""
        item = OfflineQueueItem(
            employee_id=employee_id,
            action_type=action_type,
            payload=payload,
        )
        self.db.add(item)
        await self.db.flush()
        logger.info("Queued offline operation", action=action_type, employee_id=employee_id)
        return item

    async def process_pending(self) -> dict:
        """Process all pending items. Called by Celery beat every 5 min."""
        result = await self.db.execute(
            select(OfflineQueueItem)
            .where(OfflineQueueItem.status == "pending")
            .where(OfflineQueueItem.retry_count < MAX_RETRIES)
            .order_by(OfflineQueueItem.created_at)
            .limit(50)
        )
        items = result.scalars().all()

        stats = {"processed": 0, "failed": 0, "permanent_failures": 0}

        for item in items:
            try:
                await self._execute(item)
                item.status = "done"
                item.processed_at = datetime.now(timezone.utc)
                stats["processed"] += 1

                # Notify employee of success
                await self._notify_employee(
                    item.employee_id,
                    f"✅ Queued operation completed: {item.action_type}",
                )
                logger.info("Queue item processed", id=str(item.id), action=item.action_type)

            except Exception as e:
                item.retry_count += 1
                stats["failed"] += 1

                if item.retry_count >= MAX_RETRIES:
                    item.status = "failed"
                    stats["permanent_failures"] += 1
                    await self._notify_employee(
                        item.employee_id,
                        f"❌ Operation failed after {MAX_RETRIES} retries: {item.action_type}. "
                        f"దయచేసి manually try చేయండి.",
                    )
                    logger.error(
                        "Queue item permanently failed",
                        id=str(item.id),
                        action=item.action_type,
                        error=str(e),
                    )
                else:
                    logger.warning(
                        "Queue item retry",
                        id=str(item.id),
                        retry=item.retry_count,
                        next_retry_seconds=BASE_RETRY_SECONDS * (2 ** item.retry_count),
                    )

        return stats

    async def _execute(self, item: OfflineQueueItem) -> None:
        """Execute a queued operation based on its type."""
        if item.action_type == "form_submit":
            from app.services.gsws_bridge import GSWSBridge
            bridge = GSWSBridge(db=self.db)
            submission_id = item.payload.get("submission_id")
            if submission_id:
                from uuid import UUID
                result = await bridge.submit_form(UUID(submission_id))
                if result.get("status") == "queued":
                    raise Exception("GSWS still unreachable")

        elif item.action_type == "gsws_sync":
            from app.services.gsws_bridge import GSWSBridge
            bridge = GSWSBridge(db=self.db)
            await bridge.sync_scheme_data()

        else:
            logger.warning("Unknown queue action", action=item.action_type)

    async def _notify_employee(self, employee_id: int, message: str) -> None:
        """Send WhatsApp notification to employee about queue status."""
        try:
            from app.models.user import Employee
            result = await self.db.execute(
                select(Employee).where(Employee.id == employee_id)
            )
            employee = result.scalar_one_or_none()
            if employee:
                from app.services.whatsapp_service import WhatsAppService
                wa = WhatsAppService()
                await wa.send_text(employee.phone_number, message)
        except Exception as e:
            logger.debug("Notification failed", error=str(e))

    async def get_queue_stats(self) -> dict:
        """Get queue statistics."""
        pending = await self.db.execute(
            select(func.count(OfflineQueueItem.id)).where(
                OfflineQueueItem.status == "pending"
            )
        )
        failed = await self.db.execute(
            select(func.count(OfflineQueueItem.id)).where(
                OfflineQueueItem.status == "failed"
            )
        )
        done = await self.db.execute(
            select(func.count(OfflineQueueItem.id)).where(
                OfflineQueueItem.status == "done"
            )
        )

        return {
            "pending": pending.scalar() or 0,
            "failed": failed.scalar() or 0,
            "completed": done.scalar() or 0,
        }


class KeywordFallbackSearch:
    """Offline-capable scheme search using PostgreSQL keywords (no LLM needed)."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def search(self, query: str, language: str = "te") -> str | None:
        """Search schemes by keyword when LLM is unavailable."""
        from app.core.telugu import fuzzy_match_scheme

        # 1. Try exact scheme match
        scheme_code = fuzzy_match_scheme(query)
        if scheme_code:
            return await self._get_scheme_summary(scheme_code, language)

        # 2. Keyword search in scheme names and descriptions
        results = await self.db.execute(
            select(Scheme)
            .where(Scheme.is_active.is_(True))
            .where(
                Scheme.name_te.ilike(f"%{query}%")
                | Scheme.name_en.ilike(f"%{query}%")
                | Scheme.description_te.ilike(f"%{query}%")
            )
            .limit(3)
        )
        schemes = results.scalars().all()

        if not schemes:
            return None

        # Format results without LLM
        lines = []
        for s in schemes:
            lines.append(f"📋 *{s.name_te}* ({s.name_en})")
            lines.append(f"  Department: {s.department}")
            if s.benefit_amount:
                lines.append(f"  💰 {s.benefit_amount}")
            if s.description_te:
                lines.append(f"  {s.description_te[:150]}...")
            lines.append("")

        return "\n".join(lines)

    async def _get_scheme_summary(self, scheme_code: str, language: str) -> str | None:
        """Get a formatted scheme summary from database."""
        result = await self.db.execute(
            select(Scheme).where(Scheme.scheme_code == scheme_code)
        )
        scheme = result.scalar_one_or_none()
        if not scheme:
            return None

        import json

        lines = [f"📋 *{scheme.name_te}* ({scheme.name_en})"]
        lines.append(f"Department: {scheme.department}")

        if scheme.benefit_amount:
            lines.append(f"\n💰 ప్రయోజనం: {scheme.benefit_amount}")

        if scheme.description_te and language == "te":
            lines.append(f"\n{scheme.description_te}")
        elif scheme.description_en:
            lines.append(f"\n{scheme.description_en}")

        if scheme.eligibility_criteria:
            lines.append("\n📋 అర్హత:")
            for key, value in scheme.eligibility_criteria.items():
                if isinstance(value, (list, dict)):
                    lines.append(f"  • {key}: {json.dumps(value, ensure_ascii=False)}")
                else:
                    lines.append(f"  • {key}: {value}")

        if scheme.required_documents:
            mandatory = scheme.required_documents.get("mandatory", [])
            if mandatory:
                lines.append("\n📄 Documents:")
                for doc in mandatory[:6]:
                    lines.append(f"  • {doc}")

        if scheme.go_reference:
            lines.append(f"\nGO: {scheme.go_reference}")

        return "\n".join(lines)
