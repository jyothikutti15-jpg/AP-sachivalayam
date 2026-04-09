from datetime import datetime
from pydantic import BaseModel


class CitizenResponse(BaseModel):
    id: int
    phone_number: str
    name_te: str
    name_en: str
    district: str | None = None
    mandal: str | None = None
    preferred_language: str
    is_verified: bool
    created_at: datetime
    model_config = {"from_attributes": True}


class CitizenCreateRequest(BaseModel):
    phone_number: str
    name_te: str = "Unknown"
    name_en: str = "Unknown"
    district: str | None = None
    mandal: str | None = None
    preferred_language: str = "te"
