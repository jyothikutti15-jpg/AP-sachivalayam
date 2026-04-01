from datetime import date

from sqlalchemy import Boolean, Date, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class Scheme(Base, TimestampMixin):
    __tablename__ = "schemes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    scheme_code: Mapped[str] = mapped_column(String(30), unique=True, nullable=False)
    name_te: Mapped[str] = mapped_column(Text, nullable=False)
    name_en: Mapped[str] = mapped_column(Text, nullable=False)
    department: Mapped[str] = mapped_column(String(100), nullable=False)
    description_te: Mapped[str | None] = mapped_column(Text)
    description_en: Mapped[str | None] = mapped_column(Text)
    eligibility_criteria: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    required_documents: Mapped[dict | None] = mapped_column(JSONB)
    benefit_amount: Mapped[str | None] = mapped_column(Text)
    application_process_te: Mapped[str | None] = mapped_column(Text)
    go_reference: Mapped[str | None] = mapped_column(String(100))
    effective_from: Mapped[date | None] = mapped_column(Date)
    effective_to: Mapped[date | None] = mapped_column(Date)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    metadata_extra: Mapped[dict | None] = mapped_column(JSONB)

    faqs: Mapped[list["SchemeFAQ"]] = relationship(back_populates="scheme")


class SchemeFAQ(Base, TimestampMixin):
    __tablename__ = "scheme_faqs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    scheme_id: Mapped[int] = mapped_column(ForeignKey("schemes.id"), nullable=False)
    question_te: Mapped[str] = mapped_column(Text, nullable=False)
    answer_te: Mapped[str] = mapped_column(Text, nullable=False)
    question_en: Mapped[str | None] = mapped_column(Text)
    answer_en: Mapped[str | None] = mapped_column(Text)
    frequency: Mapped[int] = mapped_column(Integer, default=0)

    scheme: Mapped[Scheme] = relationship(back_populates="faqs")
