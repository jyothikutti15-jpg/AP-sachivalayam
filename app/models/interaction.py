import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, SmallInteger, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class ChatSession(Base):
    __tablename__ = "chat_sessions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id"), nullable=False)
    channel: Mapped[str] = mapped_column(String(20), default="whatsapp")
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    intent_summary: Mapped[str | None] = mapped_column(Text)
    satisfaction_score: Mapped[int | None] = mapped_column(SmallInteger)
    metadata_extra: Mapped[dict | None] = mapped_column(JSONB)

    messages: Mapped[list["Message"]] = relationship(back_populates="session")


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("chat_sessions.id"), nullable=False
    )
    direction: Mapped[str] = mapped_column(String(4), nullable=False)  # in / out
    message_type: Mapped[str] = mapped_column(String(15), nullable=False)  # text, voice, image, button
    content_text: Mapped[str | None] = mapped_column(Text)
    content_media_url: Mapped[str | None] = mapped_column(Text)
    detected_intent: Mapped[str | None] = mapped_column(String(50))
    detected_language: Mapped[str | None] = mapped_column(String(5))
    llm_model_used: Mapped[str | None] = mapped_column(String(30))
    response_time_ms: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    session: Mapped[ChatSession] = relationship(back_populates="messages")
