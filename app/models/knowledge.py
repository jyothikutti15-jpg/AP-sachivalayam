from datetime import date

from pgvector.sqlalchemy import Vector
from sqlalchemy import Date, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class KBDocument(Base, TimestampMixin):
    __tablename__ = "kb_documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    source_type: Mapped[str | None] = mapped_column(String(30))  # GO, circular, manual, faq
    source_url: Mapped[str | None] = mapped_column(Text)
    content_te: Mapped[str | None] = mapped_column(Text)
    content_en: Mapped[str | None] = mapped_column(Text)
    department: Mapped[str | None] = mapped_column(String(100))
    published_date: Mapped[date | None] = mapped_column(Date)

    chunks: Mapped[list["KBChunk"]] = relationship(back_populates="document")


class KBChunk(Base, TimestampMixin):
    __tablename__ = "kb_chunks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("kb_documents.id"), nullable=False)
    chunk_index: Mapped[int] = mapped_column(Integer, default=0)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    language: Mapped[str] = mapped_column(String(5), default="te")
    embedding: Mapped[list[float] | None] = mapped_column(Vector(384))
    metadata_extra: Mapped[dict | None] = mapped_column(JSONB)

    document: Mapped[KBDocument] = relationship(back_populates="chunks")
