"""CLI tool to ingest documents into the knowledge base."""
import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


async def ingest_file(filepath: str, source_type: str, department: str | None):
    """Ingest a single file into the knowledge base."""
    from app.dependencies import async_session_factory
    from app.services.knowledge_indexer import KnowledgeIndexer

    path = Path(filepath)
    if not path.exists():
        print(f"Error: File not found: {filepath}")
        return

    content = path.read_text(encoding="utf-8")
    title = path.stem.replace("_", " ").title()

    # Detect language from content
    from app.core.telugu import detect_language
    language = detect_language(content)

    async with async_session_factory() as session:
        indexer = KnowledgeIndexer(db=session)
        doc = await indexer.ingest_document(
            title=title,
            content=content,
            language=language,
            source_type=source_type,
            source_url=str(path.absolute()),
            department=department,
        )
        await session.commit()
        print(f"Ingested: {title} (language={language}, doc_id={doc.id})")


async def ingest_directory(dirpath: str, source_type: str, department: str | None):
    """Ingest all text files from a directory."""
    path = Path(dirpath)
    if not path.is_dir():
        print(f"Error: Directory not found: {dirpath}")
        return

    files = list(path.glob("*.txt")) + list(path.glob("*.md"))
    print(f"Found {len(files)} files to ingest")

    for filepath in files:
        await ingest_file(str(filepath), source_type, department)


def main():
    parser = argparse.ArgumentParser(description="Ingest documents into the knowledge base")
    parser.add_argument("path", help="File or directory to ingest")
    parser.add_argument("--type", default="manual", choices=["GO", "circular", "manual", "faq"],
                       help="Source type")
    parser.add_argument("--department", help="Department name")

    args = parser.parse_args()

    path = Path(args.path)
    if path.is_dir():
        asyncio.run(ingest_directory(args.path, args.type, args.department))
    else:
        asyncio.run(ingest_file(args.path, args.type, args.department))


if __name__ == "__main__":
    main()
