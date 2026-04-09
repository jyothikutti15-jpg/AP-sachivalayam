from datetime import date

from pydantic import BaseModel


class SchemeResponse(BaseModel):
    id: int
    scheme_code: str
    name_te: str
    name_en: str
    department: str
    description_te: str | None = None
    description_en: str | None = None
    eligibility_criteria: dict
    required_documents: dict | None = None
    benefit_amount: str | None = None
    application_process_te: str | None = None
    go_reference: str | None = None
    effective_from: date | None = None
    effective_to: date | None = None
    is_active: bool

    model_config = {"from_attributes": True}


class SchemeSearchRequest(BaseModel):
    query: str
    department: str | None = None
    language: str = "te"


class SchemeSearchResponse(BaseModel):
    answer: str
    sources: list[dict] = []
    schemes_referenced: list[str] = []
    confidence: float = 0.0


class EligibilityCheckRequest(BaseModel):
    scheme_code: str
    citizen_details: dict  # age, income, caste, ration_card, etc.


class EligibilityCheckResponse(BaseModel):
    scheme_code: str
    scheme_name_te: str
    is_eligible: bool
    reasoning_te: str
    missing_documents: list[str] = []
    next_steps_te: str = ""


# --- Batch eligibility ---

class BatchEligibilityItem(BaseModel):
    """One citizen-scheme pair to evaluate."""
    citizen_id: str          # caller-supplied ID (e.g. Aadhaar hash or seq no.)
    scheme_code: str
    citizen_details: dict


class BatchEligibilityResult(EligibilityCheckResponse):
    """Single result inside a batch response — extends single-check response."""
    citizen_id: str
    error: str | None = None  # set when this specific check failed


class BatchEligibilityCheckRequest(BaseModel):
    items: list[BatchEligibilityItem]  # max 50 enforced in the endpoint


class BatchEligibilityCheckResponse(BaseModel):
    total: int
    eligible_count: int
    results: list[BatchEligibilityResult]
