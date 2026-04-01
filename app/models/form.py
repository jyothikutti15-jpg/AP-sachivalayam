import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class FormTemplate(Base, TimestampMixin):
    __tablename__ = "form_templates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name_te: Mapped[str] = mapped_column(Text, nullable=False)
    name_en: Mapped[str] = mapped_column(Text, nullable=False)
    department: Mapped[str | None] = mapped_column(String(100))
    scheme_id: Mapped[int | None] = mapped_column(ForeignKey("schemes.id"))
    fields: Mapped[dict] = mapped_column(JSONB, nullable=False)
    output_format: Mapped[str] = mapped_column(String(10), default="pdf")
    gsws_form_code: Mapped[str | None] = mapped_column(String(30))


class FormSubmission(Base):
    __tablename__ = "form_submissions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    template_id: Mapped[int] = mapped_column(ForeignKey("form_templates.id"), nullable=False)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id"), nullable=False)
    citizen_name: Mapped[str | None] = mapped_column(Text)
    citizen_aadhaar_hash: Mapped[str | None] = mapped_column(String(64))
    field_values: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    status: Mapped[str] = mapped_column(String(20), default="draft")
    gsws_submission_id: Mapped[str | None] = mapped_column(String(50))
    pdf_url: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
