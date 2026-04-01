"""
Grievance models — Tracks citizen complaints, department routing,
escalation workflows, and 72-hour resolution SLA.
"""
import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    SmallInteger,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class Grievance(Base, TimestampMixin):
    __tablename__ = "grievances"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    # Reference number for tracking (e.g., GRV-2026-0001)
    reference_number: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)

    # Who filed it
    filed_by_employee_id: Mapped[int] = mapped_column(
        ForeignKey("employees.id"), nullable=False
    )
    secretariat_id: Mapped[int | None] = mapped_column(ForeignKey("secretariats.id"))

    # Citizen details (who the grievance is about)
    citizen_name: Mapped[str] = mapped_column(Text, nullable=False)
    citizen_phone: Mapped[str | None] = mapped_column(String(15))
    citizen_aadhaar_hash: Mapped[str | None] = mapped_column(String(64))

    # Grievance content
    category: Mapped[str] = mapped_column(String(50), nullable=False)
    subcategory: Mapped[str | None] = mapped_column(String(50))
    department: Mapped[str] = mapped_column(String(100), nullable=False)
    subject_te: Mapped[str] = mapped_column(Text, nullable=False)
    description_te: Mapped[str] = mapped_column(Text, nullable=False)
    description_en: Mapped[str | None] = mapped_column(Text)

    # Routing and assignment
    assigned_to_employee_id: Mapped[int | None] = mapped_column(
        ForeignKey("employees.id")
    )
    escalation_level: Mapped[int] = mapped_column(SmallInteger, default=0)
    # 0=secretariat, 1=mandal, 2=district, 3=state

    # Status workflow
    status: Mapped[str] = mapped_column(
        String(20), default="open", nullable=False
    )
    # open -> acknowledged -> in_progress -> resolved -> closed
    # open -> acknowledged -> escalated -> resolved -> closed

    priority: Mapped[str] = mapped_column(String(10), default="medium")
    # low, medium, high, urgent

    # SLA tracking
    sla_deadline: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Resolution
    resolution_notes_te: Mapped[str | None] = mapped_column(Text)
    resolution_notes_en: Mapped[str | None] = mapped_column(Text)
    citizen_satisfaction: Mapped[int | None] = mapped_column(SmallInteger)

    # Evidence/attachments stored as JSON list of URLs
    attachment_urls: Mapped[dict | None] = mapped_column(JSONB)
    metadata_extra: Mapped[dict | None] = mapped_column(JSONB)

    is_sla_breached: Mapped[bool] = mapped_column(Boolean, default=False)

    # Relationships
    comments: Mapped[list["GrievanceComment"]] = relationship(
        back_populates="grievance", order_by="GrievanceComment.created_at"
    )


class GrievanceComment(Base):
    __tablename__ = "grievance_comments"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    grievance_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("grievances.id"), nullable=False
    )
    employee_id: Mapped[int] = mapped_column(
        ForeignKey("employees.id"), nullable=False
    )
    comment_text: Mapped[str] = mapped_column(Text, nullable=False)
    comment_type: Mapped[str] = mapped_column(String(20), default="note")
    # note, status_change, escalation, resolution
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    grievance: Mapped[Grievance] = relationship(back_populates="comments")


# Predefined grievance categories with department mapping
GRIEVANCE_CATEGORIES = {
    "agriculture": {
        "name_te": "వ్యవసాయం",
        "department": "Agriculture",
        "subcategories": ["crop_damage", "subsidy_delay", "input_supply", "insurance"],
    },
    "health": {
        "name_te": "ఆరోగ్యం",
        "department": "Health",
        "subcategories": ["hospital_service", "aarogyasri_issue", "medicine_shortage", "phc_complaint"],
    },
    "education": {
        "name_te": "విద్య",
        "department": "Education",
        "subcategories": ["school_issue", "scholarship_delay", "fee_reimbursement", "mid_day_meal"],
    },
    "welfare": {
        "name_te": "సంక్షేమం",
        "department": "Welfare",
        "subcategories": ["pension_delay", "scheme_benefit_delay", "ration_card", "housing"],
    },
    "revenue": {
        "name_te": "రెవెన్యూ",
        "department": "Revenue",
        "subcategories": ["land_issue", "pattadar_passbook", "encroachment", "survey"],
    },
    "water_supply": {
        "name_te": "నీటి సరఫరా",
        "department": "Panchayat Raj",
        "subcategories": ["drinking_water", "pipeline_damage", "bore_well", "water_quality"],
    },
    "electricity": {
        "name_te": "విద్యుత్",
        "department": "Energy",
        "subcategories": ["power_cut", "new_connection", "meter_issue", "street_light"],
    },
    "road_transport": {
        "name_te": "రోడ్లు & రవాణా",
        "department": "Roads & Buildings",
        "subcategories": ["road_damage", "bridge_issue", "bus_service", "traffic"],
    },
    "other": {
        "name_te": "ఇతరం",
        "department": "General Administration",
        "subcategories": ["corruption", "staff_behavior", "service_delay", "other"],
    },
}
