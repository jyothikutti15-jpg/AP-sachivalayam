import json

import structlog
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.telugu import fuzzy_match_scheme, normalize_telugu_text
from app.dependencies import redis_client
from app.models.knowledge import KBChunk
from app.models.scheme import Scheme, SchemeFAQ
from app.schemas.scheme import EligibilityCheckResponse, SchemeSearchResponse
from app.services.llm_service import LLMRouter

logger = structlog.get_logger()
settings = get_settings()

# Redis cache TTL
FAQ_CACHE_TTL = 3600 * 24  # 24 hours
SCHEME_CACHE_TTL = 3600 * 6  # 6 hours

SCHEME_QUERY_SYSTEM_PROMPT = """మీరు AP సచివాలయం AI సహాయకుడు. ఆంధ్రప్రదేశ్ ప్రభుత్వ పథకాల గురించి
సచివాలయం ఉద్యోగులకు సహాయం చేస్తారు.

RULES:
- Answer ONLY using the provided context. Do not make up information.
- Always respond in Telugu unless the query is in English.
- Include scheme name, eligibility criteria, required documents, and benefit amount.
- Format for WhatsApp: short paragraphs, use • for bullet points.
- If the context doesn't contain the answer, clearly say "ఈ సమాచారం నా దగ్గర లేదు."
- Cite GO numbers when available.

CONTEXT:
{context}
"""

ELIGIBILITY_SYSTEM_PROMPT = """You are an eligibility checker for AP government schemes.
Given scheme eligibility criteria and citizen details, determine if the citizen is eligible.

Respond in JSON format:
{{
    "is_eligible": true/false,
    "reasoning_te": "Telugu explanation of why eligible/not eligible",
    "missing_documents": ["list of missing documents"],
    "next_steps_te": "Telugu text for next steps"
}}

SCHEME DETAILS:
{scheme_details}
"""


class SchemeAdvisor:
    """RAG-powered scheme information and eligibility checker.

    Search chain (fast → slow):
    1. Redis FAQ cache (0ms, zero connectivity)
    2. DB FAQ keyword match (~5ms)
    3. pgvector semantic search + Claude (~2s)
    4. Keyword fallback in scheme table + Claude (~2s)
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self.llm = LLMRouter()
        self._embedding_model = None

    def _get_embedding_model(self):
        """Lazy-load embedding model (avoids loading on every request)."""
        if self._embedding_model is None:
            from sentence_transformers import SentenceTransformer
            self._embedding_model = SentenceTransformer(settings.embedding_model)
        return self._embedding_model

    async def search(
        self,
        query: str,
        department: str | None = None,
        language: str = "te",
    ) -> SchemeSearchResponse:
        """Search for scheme information using RAG pipeline."""
        normalized_query = normalize_telugu_text(query)

        # 1. Check Redis cache first (zero-latency for repeated queries)
        cached = await self._check_redis_cache(normalized_query)
        if cached:
            logger.info("FAQ cache hit", query=normalized_query[:30])
            return SchemeSearchResponse(
                answer=cached["answer"],
                schemes_referenced=cached.get("schemes", []),
                confidence=0.98,
            )

        # 2. Check if it matches a specific scheme
        scheme_code = fuzzy_match_scheme(normalized_query)
        if scheme_code:
            # Try to get FAQ answer first (DB lookup, no LLM call needed)
            faq_answer = await self._check_faqs(scheme_code, normalized_query)
            if faq_answer:
                # Cache this FAQ in Redis for next time
                await self._cache_in_redis(normalized_query, faq_answer, [scheme_code])
                return SchemeSearchResponse(
                    answer=faq_answer,
                    schemes_referenced=[scheme_code],
                    confidence=0.95,
                )

        # 2. Vector search for relevant chunks
        chunks = await self._vector_search(normalized_query, department=department, top_k=5)

        if not chunks:
            # 3. Fallback: keyword search in scheme descriptions
            schemes = await self._keyword_search(normalized_query, department)
            if schemes:
                context = self._format_scheme_context(schemes)
            else:
                return SchemeSearchResponse(
                    answer="క్షమించండి, ఈ పథకం గురించి సమాచారం దొరకలేదు. దయచేసి పథకం పేరు సరిగ్గా చెప్పండి."
                    if language == "te"
                    else "Sorry, I couldn't find information about this scheme. Please check the scheme name.",
                    confidence=0.0,
                )
        else:
            context = "\n\n---\n\n".join([c.content for c in chunks])

        # 4. Generate answer with Claude
        system_prompt = SCHEME_QUERY_SYSTEM_PROMPT.format(context=context)
        answer = await self.llm.call_claude(prompt=normalized_query, system_prompt=system_prompt)

        # Extract referenced scheme codes
        referenced = []
        if scheme_code:
            referenced.append(scheme_code)

        return SchemeSearchResponse(
            answer=answer,
            sources=[{"chunk_id": c.id, "document_id": c.document_id} for c in chunks] if chunks else [],
            schemes_referenced=referenced,
            confidence=0.85 if chunks else 0.6,
        )

    async def check_eligibility(
        self,
        scheme_code: str,
        citizen_details: dict,
    ) -> EligibilityCheckResponse:
        """Check if a citizen is eligible for a specific scheme."""
        # Fetch scheme details
        result = await self.db.execute(
            select(Scheme).where(Scheme.scheme_code == scheme_code)
        )
        scheme = result.scalar_one_or_none()

        if not scheme:
            return EligibilityCheckResponse(
                scheme_code=scheme_code,
                scheme_name_te="Unknown",
                is_eligible=False,
                reasoning_te="ఈ పథకం కనుగొనబడలేదు.",
            )

        # Build prompt with scheme criteria and citizen details
        scheme_details = json.dumps({
            "scheme_code": scheme.scheme_code,
            "name_te": scheme.name_te,
            "eligibility_criteria": scheme.eligibility_criteria,
            "required_documents": scheme.required_documents,
        }, ensure_ascii=False)

        citizen_info = json.dumps(citizen_details, ensure_ascii=False)

        prompt = f"Citizen details: {citizen_info}\n\nCheck eligibility for this scheme."
        system_prompt = ELIGIBILITY_SYSTEM_PROMPT.format(scheme_details=scheme_details)

        response = await self.llm.call_claude_structured(
            prompt=prompt,
            system_prompt=system_prompt,
        )

        # Parse JSON response
        try:
            data = json.loads(response)
        except json.JSONDecodeError:
            data = {
                "is_eligible": False,
                "reasoning_te": "అర్హత తనిఖీలో లోపం. దయచేసి మళ్ళీ ప్రయత్నించండి.",
                "missing_documents": [],
                "next_steps_te": "",
            }

        return EligibilityCheckResponse(
            scheme_code=scheme_code,
            scheme_name_te=scheme.name_te,
            is_eligible=data.get("is_eligible", False),
            reasoning_te=data.get("reasoning_te", ""),
            missing_documents=data.get("missing_documents", []),
            next_steps_te=data.get("next_steps_te", ""),
        )

    async def _check_faqs(self, scheme_code: str, query: str) -> str | None:
        """Check if a FAQ matches the query (no LLM call needed)."""
        result = await self.db.execute(
            select(SchemeFAQ)
            .join(Scheme)
            .where(Scheme.scheme_code == scheme_code)
            .order_by(SchemeFAQ.frequency.desc())
            .limit(10)
        )
        faqs = result.scalars().all()

        if not faqs:
            return None

        # Simple keyword matching against FAQ questions
        query_lower = query.lower()
        for faq in faqs:
            q_lower = (faq.question_te or "").lower()
            # If significant word overlap, return this FAQ
            query_words = set(query_lower.split())
            faq_words = set(q_lower.split())
            overlap = len(query_words & faq_words)
            if overlap >= 2:
                # Increment frequency counter
                faq.frequency += 1
                return faq.answer_te

        return None

    async def _vector_search(
        self,
        query: str,
        department: str | None = None,
        top_k: int = 5,
    ) -> list[KBChunk]:
        """Search for relevant chunks using pgvector cosine similarity."""
        try:
            # Generate embedding for query
            embedding = await self._embed_text(query)
            if not embedding:
                return []

            # Build vector search query
            sql = text("""
                SELECT id, document_id, chunk_index, content, language, metadata_extra
                FROM kb_chunks
                WHERE embedding IS NOT NULL
                ORDER BY embedding <=> :query_embedding
                LIMIT :top_k
            """)

            result = await self.db.execute(
                sql, {"query_embedding": str(embedding), "top_k": top_k}
            )
            rows = result.fetchall()

            chunks = []
            for row in rows:
                chunk = KBChunk(
                    id=row.id,
                    document_id=row.document_id,
                    chunk_index=row.chunk_index,
                    content=row.content,
                    language=row.language,
                    metadata_extra=row.metadata_extra,
                )
                chunks.append(chunk)

            return chunks
        except Exception as e:
            logger.warning("Vector search failed, falling back to keyword", error=str(e))
            return []

    async def _keyword_search(
        self,
        query: str,
        department: str | None = None,
    ) -> list[Scheme]:
        """Fallback keyword search in scheme table."""
        search_query = select(Scheme).where(Scheme.is_active.is_(True))

        if department:
            search_query = search_query.where(Scheme.department == department)

        # Simple ILIKE search on Telugu and English names/descriptions
        search_query = search_query.where(
            Scheme.name_te.ilike(f"%{query}%")
            | Scheme.name_en.ilike(f"%{query}%")
            | Scheme.description_te.ilike(f"%{query}%")
        ).limit(5)

        result = await self.db.execute(search_query)
        return list(result.scalars().all())

    def _format_scheme_context(self, schemes: list[Scheme]) -> str:
        """Format scheme data as context for LLM."""
        parts = []
        for s in schemes:
            parts.append(
                f"పథకం: {s.name_te} ({s.name_en})\n"
                f"Department: {s.department}\n"
                f"Description: {s.description_te or s.description_en or 'N/A'}\n"
                f"Eligibility: {json.dumps(s.eligibility_criteria, ensure_ascii=False)}\n"
                f"Documents: {json.dumps(s.required_documents, ensure_ascii=False) if s.required_documents else 'N/A'}\n"
                f"Benefit: {s.benefit_amount or 'N/A'}\n"
                f"GO: {s.go_reference or 'N/A'}"
            )
        return "\n\n---\n\n".join(parts)

    async def _embed_text(self, text: str) -> list[float] | None:
        """Generate embedding for text using sentence-transformers."""
        try:
            model = self._get_embedding_model()
            embedding = model.encode(text).tolist()
            return embedding
        except Exception as e:
            logger.error("Embedding generation failed", error=str(e))
            return None

    # --- Redis Caching Layer ---

    async def _check_redis_cache(self, query: str) -> dict | None:
        """Check if this query has a cached response in Redis."""
        try:
            import hashlib
            cache_key = f"faq:{hashlib.md5(query.encode()).hexdigest()}"
            cached = await redis_client.get(cache_key)
            if cached:
                return json.loads(cached)
        except Exception as e:
            logger.debug("Redis cache miss or error", error=str(e))
        return None

    async def _cache_in_redis(
        self, query: str, answer: str, schemes: list[str] | None = None
    ) -> None:
        """Cache a query-answer pair in Redis."""
        try:
            import hashlib
            cache_key = f"faq:{hashlib.md5(query.encode()).hexdigest()}"
            data = json.dumps({"answer": answer, "schemes": schemes or []}, ensure_ascii=False)
            await redis_client.setex(cache_key, FAQ_CACHE_TTL, data)
            logger.debug("Cached FAQ in Redis", key=cache_key[:20])
        except Exception as e:
            logger.debug("Redis cache write failed", error=str(e))

    async def warm_faq_cache(self) -> int:
        """Pre-load top FAQs into Redis cache. Call on startup or via Celery."""
        result = await self.db.execute(
            select(SchemeFAQ, Scheme)
            .join(Scheme)
            .order_by(SchemeFAQ.frequency.desc())
            .limit(200)
        )
        rows = result.all()

        cached = 0
        for faq, scheme in rows:
            if faq.question_te and faq.answer_te:
                normalized = normalize_telugu_text(faq.question_te)
                await self._cache_in_redis(normalized, faq.answer_te, [scheme.scheme_code])
                cached += 1

            if faq.question_en and faq.answer_en:
                normalized = normalize_telugu_text(faq.question_en)
                await self._cache_in_redis(normalized, faq.answer_en, [scheme.scheme_code])
                cached += 1

        logger.info("FAQ cache warmed", count=cached)
        return cached
