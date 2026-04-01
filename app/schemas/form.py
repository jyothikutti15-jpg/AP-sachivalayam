from uuid import UUID

from pydantic import BaseModel


class FormTemplateResponse(BaseModel):
    id: int
    name_te: str
    name_en: str
    department: str | None = None
    fields: dict
    output_format: str
    gsws_form_code: str | None = None

    model_config = {"from_attributes": True}


class AutoFillRequest(BaseModel):
    template_id: int
    employee_id: int
    input_text: str
    citizen_name: str | None = None


class AutoFillResponse(BaseModel):
    submission_id: UUID
    extracted_fields: dict
    confidence_scores: dict[str, float] = {}
    status: str = "draft"
    message_te: str = ""
