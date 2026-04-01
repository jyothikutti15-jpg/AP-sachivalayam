"""Telugu-aware text chunking for the knowledge base."""
from app.core.telugu import split_telugu_sentences


def chunk_text(
    text: str,
    language: str = "te",
    chunk_size: int = 500,
    overlap: int = 50,
) -> list[str]:
    """Split text into overlapping chunks respecting sentence boundaries."""
    if language == "te":
        sentences = split_telugu_sentences(text)
    else:
        sentences = [s.strip() for s in text.split(".") if s.strip()]

    if not sentences:
        return [text] if text.strip() else []

    chunks = []
    current_chunk: list[str] = []
    current_length = 0

    for sentence in sentences:
        word_count = len(sentence.split())

        if current_length + word_count > chunk_size and current_chunk:
            chunks.append(" ".join(current_chunk))
            # Overlap: keep last N words
            overlap_words = " ".join(current_chunk).split()[-overlap:]
            current_chunk = [" ".join(overlap_words)]
            current_length = len(overlap_words)

        current_chunk.append(sentence)
        current_length += word_count

    if current_chunk:
        chunks.append(" ".join(current_chunk))

    return chunks
