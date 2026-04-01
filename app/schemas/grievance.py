from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class GrievanceCreateRequest(BaseModel):
    citizen_name: str
    citizen_phone: str | None = None
    category: str
    subcategory: str | None = None
    department: str | None = None  # auto-detected from category if not provided
    subject_te: str
    description_te: str
    description_en: str | None = None
    priority: str = "medium"
    attachment_urls: list[str] | None = None


class GrievanceResponse(BaseModel):
    id: UUID
    reference_number: str
    citizen_name: str
    category: str
    department: str
    subject_te: str
    description_te: str
    status: str
    priority: str
    escalation_level: int
    sla_deadline: datetime | None = None
    acknowledged_at: datetime | None = None
    resolved_at: datetime | None = None
    is_sla_breached: bool
    resolution_notes_te: str | None = None
    created_at: datetime
    updated_at: datetime
    comments: list["GrievanceCommentResponse"] = []

    model_config = {"from_attributes": True}


class GrievanceCommentResponse(BaseModel):
    id: UUID
    employee_id: int
    comment_text: str
    comment_type: str
    created_at: datetime

    model_config = {"from_attributes": True}


class GrievanceListResponse(BaseModel):
    grievances: list[GrievanceResponse]
    total: int
    page: int
    page_size: int


class GrievanceUpdateRequest(BaseModel):
    status: str | None = None
    priority: str | None = None
    assigned_to_employee_id: int | None = None
    resolution_notes_te: str | None = None
    resolution_notes_en: str | None = None
    citizen_satisfaction: int | None = None


class GrievanceCommentRequest(BaseModel):
    comment_text: str
    comment_type: str = "note"


class GrievanceAISuggestResponse(BaseModel):
    suggested_category: str
    suggested_department: str
    suggested_priority: str
    escalation_path_te: str
    required_evidence_te: list[str]
    similar_grievances: list[str] = []
    resolution_suggestion_te: str
