"""Citizen model — for citizens using the WhatsApp bot (read-only access)."""
from sqlalchemy import Integer, String, Text, Boolean
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class Citizen(Base, TimestampMixin):
    __tablename__ = "citizens"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    phone_number: Mapped[str] = mapped_column(String(15), unique=True, nullable=False, index=True)
    name_te: Mapped[str] = mapped_column(Text, default="Unknown")
    name_en: Mapped[str] = mapped_column(Text, default="Unknown")
    district: Mapped[str | None] = mapped_column(String(50))
    mandal: Mapped[str | None] = mapped_column(String(50))
    preferred_language: Mapped[str] = mapped_column(String(5), default="te")
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False)
