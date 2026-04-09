"""
GO/Circular Knowledge Base — RAG search over government orders and circulars.

Employees can ask questions like:
- "What changed in Amma Vodi eligibility in March 2026?"
- "Show me recent GOs for the Education department"
- "Is there a new circular about pension increase?"
"""

import json
from datetime import date

import structlog
from sqlalchemy import select, and_, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.circular import Circular
from app.schemas.circular import (
    CircularCreate,
    CircularResponse,
    CircularSearchResponse,
)
from app.services.llm_service import LLMRouter

logger = structlog.get_logger()

CIRCULAR_SEARCH_PROMPT = """మీరు AP ప్రభుత్వ ఉత్తర్వులు (GOs) మరియు సర్క్యులర్ల నిపుణుడు.
ఉద్యోగి అడిగిన ప్రశ్నకు క్రింద ఇచ్చిన GO/సర్క్యులర్ సమాచారం ఆధారంగా సమాధానం ఇవ్వండి.

RULES:
- Answer ONLY using the provided circulars. Do not fabricate GO numbers or dates.
- Always respond in Telugu unless the query is in English.
- Cite the GO reference number (e.g., G.O.Ms.No.21) in your answer.
- Highlight key changes clearly with bullet points.
- If the information is not available, say "ఈ GO/సర్క్యులర్ సమాచారం నా దగ్గర లేదు."

CIRCULARS:
{circulars_context}
"""

CIRCULAR_SUMMARY_PROMPT = """Summarize this AP government order/circular in Telugu.
Extract and structure the following:
1. Main purpose / subject
2. Key changes or new rules
3. Who is affected (departments, employees, citizens)
4. Effective date
5. Any deadlines or action items

Keep the summary concise (3-5 bullet points). Respond in JSON:
{{
    "summary_te": "Telugu summary with bullet points",
    "summary_en": "English summary",
    "key_changes": [
        {{"field": "what changed", "description_te": "Telugu description"}}
    ],
    "tags": ["tag1", "tag2"]
}}

CIRCULAR CONTENT:
{content}
"""


class CircularService:
    """Manages government orders/circulars with RAG search."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.llm = LLMRouter()

    async def create_circular(self, data: CircularCreate) -> Circular:
        """Create a new circular/GO entry."""
        circular = Circular(
            reference_number=data.reference_number,
            title_te=data.title_te,
            title_en=data.title_en,
            content_te=data.content_te,
            content_en=data.content_en,
            summary_te=data.summary_te,
            summary_en=data.summary_en,
            department=data.department,
            category=data.category,
            scheme_code=data.scheme_code,
            issued_date=data.issued_date,
            effective_date=data.effective_date,
            expiry_date=data.expiry_date,
            source_url=data.source_url,
            pdf_url=data.pdf_url,
            impact_level=data.impact_level,
            key_changes=data.key_changes,
            affected_districts=data.affected_districts,
            tags=data.tags,
        )
        self.db.add(circular)
        await self.db.flush()
        await self.db.refresh(circular)
        logger.info("Circular created", reference=data.reference_number)
        return circular

    async def search(
        self,
        query: str,
        department: str | None = None,
        scheme_code: str | None = None,
        from_date: date | None = None,
        to_date: date | None = None,
        language: str = "te",
    ) -> CircularSearchResponse:
        """Search circulars using keyword matching + LLM answer generation."""

        # Build filter query
        filters = [Circular.is_active.is_(True)]
        if department:
            filters.append(Circular.department == department)
        if scheme_code:
            filters.append(Circular.scheme_code == scheme_code)
        if from_date:
            filters.append(Circular.issued_date >= from_date)
        if to_date:
            filters.append(Circular.issued_date <= to_date)

        # Keyword search across title and content
        search_query = (
            select(Circular)
            .where(and_(*filters))
            .where(
                Circular.title_te.ilike(f"%{query}%")
                | Circular.title_en.ilike(f"%{query}%")
                | Circular.content_te.ilike(f"%{query}%")
                | Circular.content_en.ilike(f"%{query}%")
                | Circular.reference_number.ilike(f"%{query}%")
            )
            .order_by(desc(Circular.issued_date))
            .limit(10)
        )

        result = await self.db.execute(search_query)
        circulars = list(result.scalars().all())

        # If no keyword match, try broader date-based search
        if not circulars and (from_date or to_date):
            broad_query = (
                select(Circular)
                .where(and_(*filters))
                .order_by(desc(Circular.issued_date))
                .limit(10)
            )
            result = await self.db.execute(broad_query)
            circulars = list(result.scalars().all())

        if not circulars:
            no_result_msg = (
                "ఈ GO/సర్క్యులర్ సమాచారం దొరకలేదు. దయచేసి GO నంబర్ లేదా విషయం మళ్ళీ చెప్పండి."
                if language == "te"
                else "No matching circulars found. Please try with a GO number or different keywords."
            )
            return CircularSearchResponse(answer=no_result_msg, confidence=0.0)

        # Increment view counts
        for c in circulars:
            c.view_count += 1

        # Build context and generate answer with LLM
        context = self._format_circular_context(circulars)
        system_prompt = CIRCULAR_SEARCH_PROMPT.format(circulars_context=context)

        answer = await self.llm.call_claude(
            prompt=query,
            system_prompt=system_prompt,
            max_tokens=1500,
        )

        circular_responses = [
            CircularResponse(
                id=str(c.id),
                reference_number=c.reference_number,
                title_te=c.title_te,
                title_en=c.title_en,
                summary_te=c.summary_te,
                summary_en=c.summary_en,
                department=c.department,
                category=c.category,
                scheme_code=c.scheme_code,
                issued_date=c.issued_date,
                effective_date=c.effective_date,
                impact_level=c.impact_level,
                key_changes=c.key_changes,
                tags=c.tags,
                is_active=c.is_active,
                source_url=c.source_url,
            )
            for c in circulars
        ]

        return CircularSearchResponse(
            answer=answer,
            circulars_referenced=circular_responses,
            confidence=0.85 if len(circulars) > 0 else 0.0,
        )

    async def list_recent(
        self,
        department: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> list[Circular]:
        """List recent circulars, optionally filtered by department."""
        query = (
            select(Circular)
            .where(Circular.is_active.is_(True))
            .order_by(desc(Circular.issued_date))
        )
        if department:
            query = query.where(Circular.department == department)
        query = query.offset(offset).limit(limit)

        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_by_reference(self, reference_number: str) -> Circular | None:
        """Get a circular by its GO reference number."""
        result = await self.db.execute(
            select(Circular).where(Circular.reference_number == reference_number)
        )
        circular = result.scalar_one_or_none()
        if circular:
            circular.view_count += 1
        return circular

    async def auto_summarize(
        self,
        content: str,
    ) -> dict:
        """Use AI to generate a summary and extract key changes from a GO."""
        system_prompt = CIRCULAR_SUMMARY_PROMPT.format(content=content)
        try:
            response = await self.llm.call_claude_structured(
                prompt="Summarize this government order.",
                system_prompt=system_prompt,
                max_tokens=1500,
            )
            return json.loads(response)
        except (json.JSONDecodeError, Exception) as e:
            logger.error("Circular summarization failed", error=str(e))
            return {
                "summary_te": "సారాంశం తయారు చేయడంలో లోపం.",
                "summary_en": "Failed to generate summary.",
                "key_changes": [],
                "tags": [],
            }

    def _format_circular_context(self, circulars: list[Circular]) -> str:
        """Format circulars as context for LLM."""
        parts = []
        for c in circulars:
            changes_str = ""
            if c.key_changes:
                changes_str = "\nKey Changes: " + json.dumps(
                    c.key_changes, ensure_ascii=False
                )
            parts.append(
                f"GO: {c.reference_number}\n"
                f"Title: {c.title_te}\n"
                f"Department: {c.department}\n"
                f"Issued: {c.issued_date}\n"
                f"Impact: {c.impact_level}\n"
                f"Content: {c.content_te or c.summary_te or 'N/A'}"
                f"{changes_str}"
            )
        return "\n\n---\n\n".join(parts)
