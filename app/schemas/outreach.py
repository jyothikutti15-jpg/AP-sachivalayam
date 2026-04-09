"""Pydantic schemas for the Proactive Scheme Outreach feature."""
from datetime import datetime

from pydantic import BaseModel


class BeneficiaryCreateRequest(BaseModel):
    aadhaar_hash: str | None = None
    phone_number: str | None = None
    name_te: str
    name_en: str | None = None
    age: int | None = None
    gender: str | None = None
    caste_category: str | None = None
    annual_income: int | None = None
    ration_card_type: str | None = None
    district: str | None = None
    mandal: str | None = None
    secretariat_id: int | None = None
    is_disabled: bool = False
    disability_percentage: int | None = None
    occupation: str | None = None
    land_acres_wet: float | None = None
    land_acres_dry: float | None = None
    num_children: int | None = None
    is_govt_employee: bool = False
    is_income_tax_payer: bool = False
    owns_four_wheeler: bool = False
    electricity_units: int | None = None
    schemes_enrolled: list[str] | None = None
    opt_out: bool = False


class BeneficiaryResponse(BaseModel):
    id: int
    name_te: str
    name_en: str | None = None
    age: int | None = None
    gender: str | None = None
    caste_category: str | None = None
    annual_income: int | None = None
    ration_card_type: str | None = None
    district: str | None = None
    mandal: str | None = None
    secretariat_id: int | None = None
    is_disabled: bool = False
    occupation: str | None = None
    schemes_enrolled: list[str] | None = None
    created_at: datetime | None = None

    model_config = {"from_attributes": True}


class OutreachMatchResponse(BaseModel):
    beneficiary_id: int
    beneficiary_name: str
    scheme_code: str
    scheme_name: str
    match_score: float
    reasoning: str


class OutreachListItem(BaseModel):
    id: str
    beneficiary_id: int
    beneficiary_name: str
    beneficiary_phone: str | None = None
    scheme_code: str
    match_score: float
    reasoning: str | None = None
    status: str
    created_at: str | None = None


class OutreachListResponse(BaseModel):
    items: list[OutreachListItem]
    total: int
    limit: int
    offset: int


class OutreachScanResponse(BaseModel):
    secretariat_id: int
    matches_found: int
    matches: list[OutreachMatchResponse]


class BeneficiaryEligibleSchemesResponse(BaseModel):
    beneficiary_id: int
    eligible_schemes: list[dict]


class OutreachStatusUpdateResponse(BaseModel):
    id: str
    status: str
