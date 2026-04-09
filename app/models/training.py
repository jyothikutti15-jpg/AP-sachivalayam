"""Training models — Tracks employee training sessions and scores."""
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, SmallInteger, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class TrainingSession(Base, TimestampMixin):
    __tablename__ = "training_sessions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id"), nullable=False)
    scenario_id: Mapped[str] = mapped_column(String(10), nullable=False)
    difficulty: Mapped[str] = mapped_column(String(10), default="easy")
    category: Mapped[str] = mapped_column(String(30), default="scheme_query")
    employee_response: Mapped[str | None] = mapped_column(Text)
    ai_score: Mapped[int | None] = mapped_column(SmallInteger)  # 0-100
    ai_feedback_te: Mapped[str | None] = mapped_column(Text)
    ai_feedback_en: Mapped[str | None] = mapped_column(Text)
    key_points_covered: Mapped[dict | None] = mapped_column(JSONB)
    time_taken_seconds: Mapped[int | None] = mapped_column(Integer)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
