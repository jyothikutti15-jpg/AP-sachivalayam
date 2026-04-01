"""
Duplicate Detection — Identifies potential duplicate grievances
using fuzzy string matching on descriptions and citizen identifiers.
"""
from datetime import datetime, timedelta, timezone

import structlog
from rapidfuzz import fuzz
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.grievance import Grievance

logger = structlog.get_logger()

SIMILARITY_THRESHOLD = 75


class DuplicateDetector:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def find_similar_grievances(
        self,
        citizen_phone: str | None,
        description_te: str,
        category: str,
        limit: int = 5,
        days_lookback: int = 30,
    ) -> list[dict]:
        """Find potentially duplicate grievances using fuzzy matching."""
        cutoff = datetime.now(timezone.utc) - timedelta(days=days_lookback)

        query = select(Grievance).where(
            Grievance.category == category,
            Grievance.created_at >= cutoff,
        )
        if citizen_phone:
            query = query.where(Grievance.citizen_phone == citizen_phone)
        query = query.order_by(Grievance.created_at.desc()).limit(50)

        result = await self.db.execute(query)
        existing = result.scalars().all()

        candidates = []
        for g in existing:
            score = fuzz.token_sort_ratio(description_te, g.description_te)
            if score >= SIMILARITY_THRESHOLD:
                candidates.append({
                    "grievance_id": str(g.id),
                    "reference_number": g.reference_number,
                    "similarity_score": round(score / 100.0, 2),
                    "subject_te": g.subject_te,
                    "status": g.status,
                })

        candidates.sort(key=lambda x: x["similarity_score"], reverse=True)
        return candidates[:limit]

    async def check_before_filing(
        self, citizen_phone: str | None, description_te: str, category: str
    ) -> dict | None:
        """Quick check for high-confidence duplicates. Returns top match or None."""
        similar = await self.find_similar_grievances(
            citizen_phone, description_te, category, limit=1
        )
        if similar and similar[0]["similarity_score"] >= 0.85:
            return similar[0]
        return None
