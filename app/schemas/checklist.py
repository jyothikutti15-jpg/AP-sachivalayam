"""Schemas for Document Checklist Generator (Feature 8)."""

from pydantic import BaseModel


class CitizenProfile(BaseModel):
    """Citizen details used to determine scheme eligibility and required documents."""
    name: str | None = None
    age: int | None = None
    gender: str | None = None  # male, female, other
    income: int | None = None  # annual household income in INR
    caste: str | None = None   # OC, BC, SC, ST, EBC, Kapu, Minority
    ration_card: str | None = None  # white, pink, antyodaya, none
    occupation: str | None = None
    district: str | None = None
    is_disabled: bool = False
    disability_percentage: int | None = None
    land_acres: float | None = None
    has_school_children: bool = False
    num_children: int | None = None
    is_widow: bool = False
    is_pregnant: bool = False
    education_level: str | None = None  # illiterate, primary, secondary, graduate, post_graduate


class DocumentItem(BaseModel):
    """A single document in the checklist."""
    document_name_te: str
    document_name_en: str
    is_common: bool = False       # shared across multiple schemes
    required_for_schemes: list[str] = []  # scheme codes that need this
    notes_te: str = ""            # e.g. "self-attested copy" or "original required"


class SchemeDocumentGroup(BaseModel):
    """Documents grouped by scheme."""
    scheme_code: str
    scheme_name_te: str
    scheme_name_en: str
    is_eligible: bool
    confidence: float = 0.0
    documents: list[str] = []
    eligibility_reason_te: str = ""


class DocumentChecklistResponse(BaseModel):
    """Full checklist response with common docs + per-scheme breakdown."""
    citizen_name: str | None = None
    total_eligible_schemes: int = 0
    common_documents: list[DocumentItem] = []
    scheme_documents: list[SchemeDocumentGroup] = []
    total_unique_documents: int = 0
    ai_summary_te: str = ""
