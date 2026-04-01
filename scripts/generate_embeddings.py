"""
Generate embeddings for all scheme data and store in pgvector.

This script:
1. Reads all scheme JSON files
2. Creates knowledge base documents from scheme content
3. Chunks the content (Telugu-aware)
4. Generates embeddings using multilingual model
5. Stores everything in PostgreSQL with pgvector

Run: python scripts/generate_embeddings.py
"""
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.dependencies import async_session_factory, engine
from app.models import Base


SCHEMES_DIR = Path(__file__).parent.parent / "app" / "data" / "schemes"


def scheme_to_knowledge_text(scheme: dict) -> tuple[str, str]:
    """Convert a scheme JSON into a rich text document for embedding.

    Returns (telugu_text, english_text)
    """
    # Build comprehensive Telugu text for embedding
    te_parts = []
    te_parts.append(f"పథకం పేరు: {scheme['name_te']}")
    te_parts.append(f"Scheme: {scheme['name_en']}")
    te_parts.append(f"Department: {scheme['department']}")

    if scheme.get("description_te"):
        te_parts.append(f"వివరణ: {scheme['description_te']}")

    # Eligibility as readable text
    eligibility = scheme.get("eligibility_criteria", {})
    if eligibility:
        te_parts.append("అర్హత:")
        for key, value in eligibility.items():
            if isinstance(value, list):
                te_parts.append(f"  {key}: {', '.join(str(v) for v in value)}")
            elif isinstance(value, dict):
                for sub_key, sub_val in value.items():
                    te_parts.append(f"  {sub_key}: {sub_val}")
            else:
                te_parts.append(f"  {key}: {value}")

    # Documents
    docs = scheme.get("required_documents", {})
    if docs:
        mandatory = docs.get("mandatory", [])
        if mandatory:
            te_parts.append("అవసరమైన documents:")
            for doc in mandatory:
                te_parts.append(f"  • {doc}")

    if scheme.get("benefit_amount"):
        te_parts.append(f"ప్రయోజనం: {scheme['benefit_amount']}")

    if scheme.get("application_process_te"):
        te_parts.append(f"దరఖాస్తు ప్రక్రియ:\n{scheme['application_process_te']}")

    if scheme.get("go_reference"):
        te_parts.append(f"GO Reference: {scheme['go_reference']}")

    telugu_text = "\n".join(te_parts)

    # Build English text
    en_parts = []
    en_parts.append(f"Scheme: {scheme['name_en']} ({scheme['name_te']})")
    en_parts.append(f"Department: {scheme['department']}")
    if scheme.get("description_en"):
        en_parts.append(f"Description: {scheme['description_en']}")
    if scheme.get("benefit_amount"):
        en_parts.append(f"Benefit: {scheme['benefit_amount']}")

    english_text = "\n".join(en_parts)

    return telugu_text, english_text


async def generate_all_embeddings():
    """Main pipeline to generate embeddings for all schemes."""
    from app.services.knowledge_indexer import KnowledgeIndexer

    # Create tables if they don't exist
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    scheme_files = sorted(SCHEMES_DIR.glob("*.json"))
    print(f"Found {len(scheme_files)} scheme files")

    async with async_session_factory() as session:
        indexer = KnowledgeIndexer(db=session)
        total_chunks = 0

        for filepath in scheme_files:
            with open(filepath, encoding="utf-8") as f:
                scheme = json.load(f)

            scheme_code = scheme["scheme_code"]
            te_text, en_text = scheme_to_knowledge_text(scheme)

            print(f"\nProcessing: {scheme['name_en']} ({scheme_code})")
            print(f"  Telugu text: {len(te_text)} chars")
            print(f"  English text: {len(en_text)} chars")

            # Ingest Telugu version
            te_doc = await indexer.ingest_document(
                title=f"{scheme['name_te']} ({scheme['name_en']})",
                content=te_text,
                language="te",
                source_type="scheme",
                department=scheme["department"],
                metadata={"scheme_code": scheme_code},
            )

            # Ingest English version
            en_doc = await indexer.ingest_document(
                title=f"{scheme['name_en']}",
                content=en_text,
                language="en",
                source_type="scheme",
                department=scheme["department"],
                metadata={"scheme_code": scheme_code},
            )

            # Count chunks created
            from sqlalchemy import func, select
            from app.models.knowledge import KBChunk
            chunk_count = await session.execute(
                select(func.count(KBChunk.id)).where(
                    KBChunk.document_id.in_([te_doc.id, en_doc.id])
                )
            )
            doc_chunks = chunk_count.scalar() or 0
            total_chunks += doc_chunks
            print(f"  Chunks created: {doc_chunks}")

        await session.commit()

        print(f"\n{'=' * 50}")
        print(f"EMBEDDING GENERATION COMPLETE")
        print(f"Schemes processed: {len(scheme_files)}")
        print(f"Total chunks with embeddings: {total_chunks}")
        print(f"Embedding model: paraphrase-multilingual-MiniLM-L12-v2")
        print(f"Vector dimension: 384")


async def stats():
    """Show embedding statistics."""
    from sqlalchemy import func, select
    from app.models.knowledge import KBChunk, KBDocument

    async with async_session_factory() as session:
        doc_count = await session.execute(select(func.count(KBDocument.id)))
        chunk_count = await session.execute(select(func.count(KBChunk.id)))
        embedded_count = await session.execute(
            select(func.count(KBChunk.id)).where(KBChunk.embedding.isnot(None))
        )

        print(f"Documents: {doc_count.scalar()}")
        print(f"Total chunks: {chunk_count.scalar()}")
        print(f"Chunks with embeddings: {embedded_count.scalar()}")


if __name__ == "__main__":
    if "--stats" in sys.argv:
        asyncio.run(stats())
    else:
        print("AP Sachivalayam — Embedding Generation Pipeline")
        print("=" * 50)
        asyncio.run(generate_all_embeddings())
