import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.telugu import split_telugu_sentences
from app.models.knowledge import KBChunk, KBDocument

logger = structlog.get_logger()
settings = get_settings()


class KnowledgeIndexer:
    """Ingests documents, chunks them, generates embeddings, and stores in pgvector."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self._model = None

    def _get_embedding_model(self):
        """Lazy-load the embedding model."""
        if self._model is None:
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer(settings.embedding_model)
        return self._model

    async def ingest_document(
        self,
        title: str,
        content: str,
        language: str = "te",
        source_type: str = "manual",
        source_url: str | None = None,
        department: str | None = None,
        metadata: dict | None = None,
    ) -> KBDocument:
        """Ingest a single document: store, chunk, embed."""
        # 1. Create document record
        doc = KBDocument(
            title=title,
            source_type=source_type,
            source_url=source_url,
            department=department,
        )
        if language == "te":
            doc.content_te = content
        else:
            doc.content_en = content

        self.db.add(doc)
        await self.db.flush()

        # 2. Chunk the content
        chunks = self._chunk_text(content, language=language, chunk_size=500, overlap=50)

        # 3. Generate embeddings and store chunks
        model = self._get_embedding_model()

        for i, chunk_text in enumerate(chunks):
            embedding = model.encode(chunk_text).tolist()

            chunk = KBChunk(
                document_id=doc.id,
                chunk_index=i,
                content=chunk_text,
                language=language,
                embedding=embedding,
                metadata_extra={
                    "department": department,
                    **(metadata or {}),
                },
            )
            self.db.add(chunk)

        await self.db.flush()
        logger.info(
            "Document ingested",
            title=title,
            chunks=len(chunks),
            language=language,
        )
        return doc

    def _chunk_text(
        self,
        text: str,
        language: str = "te",
        chunk_size: int = 500,
        overlap: int = 50,
    ) -> list[str]:
        """Split text into overlapping chunks, respecting sentence boundaries."""
        if language == "te":
            sentences = split_telugu_sentences(text)
        else:
            sentences = [s.strip() for s in text.split(".") if s.strip()]

        chunks = []
        current_chunk: list[str] = []
        current_length = 0

        for sentence in sentences:
            sentence_len = len(sentence.split())

            if current_length + sentence_len > chunk_size and current_chunk:
                chunks.append(" ".join(current_chunk))

                # Keep overlap sentences
                overlap_text = " ".join(current_chunk)
                overlap_words = overlap_text.split()[-overlap:]
                current_chunk = [" ".join(overlap_words)]
                current_length = len(overlap_words)

            current_chunk.append(sentence)
            current_length += sentence_len

        if current_chunk:
            chunks.append(" ".join(current_chunk))

        return chunks

    async def reindex_all(self) -> int:
        """Reindex all documents (regenerate embeddings)."""
        from sqlalchemy import select

        result = await self.db.execute(select(KBDocument))
        documents = result.scalars().all()

        total_chunks = 0
        for doc in documents:
            content = doc.content_te or doc.content_en or ""
            language = "te" if doc.content_te else "en"

            if content:
                chunks = self._chunk_text(content, language=language)
                model = self._get_embedding_model()

                for i, chunk_text in enumerate(chunks):
                    embedding = model.encode(chunk_text).tolist()
                    chunk = KBChunk(
                        document_id=doc.id,
                        chunk_index=i,
                        content=chunk_text,
                        language=language,
                        embedding=embedding,
                    )
                    self.db.add(chunk)
                    total_chunks += 1

        await self.db.flush()
        logger.info("Reindex complete", total_chunks=total_chunks)
        return total_chunks
