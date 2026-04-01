from pydantic import BaseModel


class TranscriptionResponse(BaseModel):
    text: str
    language: str
    confidence: float = 0.0
    duration_seconds: float = 0.0
    entities: dict = {}  # extracted names, numbers, scheme references
