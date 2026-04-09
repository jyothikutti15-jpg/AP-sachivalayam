from pydantic import BaseModel


class OCRResult(BaseModel):
    document_type: str
    extracted_fields: dict
    confidence: float = 0.0
    aadhaar_hash: str | None = None
    aadhaar_last4: str | None = None
    form_field_mapping: dict | None = None
    message_te: str | None = None
    message_en: str | None = None
