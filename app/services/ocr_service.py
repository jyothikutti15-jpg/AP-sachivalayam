"""Document OCR Service — Extracts fields from Aadhaar/ration cards using Claude Vision."""
import base64
import json

import structlog

from app.core.security import hash_aadhaar, mask_aadhaar
from app.services.llm_service import LLMRouter

logger = structlog.get_logger()

DOCUMENT_DETECTION_PROMPT = """Identify the type of Indian government document in this image.
Respond with ONLY one of: aadhaar_card, ration_card, income_certificate, caste_certificate, bank_passbook, driving_license, voter_id, other, not_a_document"""

AADHAAR_EXTRACTION_PROMPT = """Extract ALL fields from this Aadhaar card image. Return ONLY valid JSON:
{
    "name": "Full name as printed",
    "name_te": "Telugu name if visible",
    "date_of_birth": "DD/MM/YYYY",
    "gender": "Male/Female/Other",
    "aadhaar_number": "XXXX XXXX XXXX (full 12 digits)",
    "address": "Full address",
    "pin_code": "6 digit PIN",
    "father_name": "Father/Husband name if visible",
    "confidence": 0.0-1.0
}
If a field is not visible, set it to null."""

RATION_CARD_EXTRACTION_PROMPT = """Extract ALL fields from this Indian ration card image. Return ONLY valid JSON:
{
    "card_number": "Ration card number",
    "card_type": "White/Rice/Antyodaya/Pink",
    "head_of_family": "Name of household head",
    "address": "Full address",
    "num_members": number of family members,
    "members": [{"name": "...", "age": ..., "relation": "..."}],
    "district": "District name",
    "mandal": "Mandal name",
    "confidence": 0.0-1.0
}
If a field is not visible, set it to null."""

GENERIC_EXTRACTION_PROMPT = """Extract ALL visible text fields from this Indian government document. Return ONLY valid JSON:
{
    "document_type": "type of document",
    "fields": {"field_name": "field_value", ...},
    "confidence": 0.0-1.0
}"""


class OCRService:
    """Extracts structured data from government document images using Claude Vision."""

    def __init__(self):
        self.llm = LLMRouter()

    async def detect_document_type(self, image_bytes: bytes) -> str:
        """Identify the type of document in the image."""
        try:
            result = await self.llm.call_claude_vision(
                image_bytes=image_bytes,
                prompt=DOCUMENT_DETECTION_PROMPT,
                max_tokens=50,
            )
            doc_type = result.strip().lower().replace(" ", "_")
            valid_types = {
                "aadhaar_card", "ration_card", "income_certificate",
                "caste_certificate", "bank_passbook", "driving_license",
                "voter_id", "other", "not_a_document",
            }
            return doc_type if doc_type in valid_types else "other"
        except Exception as e:
            logger.error("Document detection failed", error=str(e))
            return "other"

    async def extract_document_fields(
        self, image_bytes: bytes, document_type: str | None = None
    ) -> dict:
        """Extract structured fields from a document image."""
        if not document_type:
            document_type = await self.detect_document_type(image_bytes)

        prompt_map = {
            "aadhaar_card": AADHAAR_EXTRACTION_PROMPT,
            "ration_card": RATION_CARD_EXTRACTION_PROMPT,
        }
        prompt = prompt_map.get(document_type, GENERIC_EXTRACTION_PROMPT)

        try:
            result = await self.llm.call_claude_vision(
                image_bytes=image_bytes,
                prompt=prompt,
                max_tokens=1500,
            )

            # Parse JSON from response
            data = self._parse_json_response(result)
            data["document_type"] = document_type

            # Secure Aadhaar handling
            if document_type == "aadhaar_card" and data.get("aadhaar_number"):
                raw = data["aadhaar_number"].replace(" ", "")
                if len(raw) == 12 and raw.isdigit():
                    data["aadhaar_hash"] = hash_aadhaar(raw)
                    data["aadhaar_last4"] = raw[-4:]
                    data["aadhaar_number"] = mask_aadhaar(raw)  # Never store raw

            logger.info(
                "OCR extraction complete",
                document_type=document_type,
                fields_extracted=len(data),
            )
            return data

        except Exception as e:
            logger.error("OCR extraction failed", error=str(e))
            return {"document_type": document_type, "error": str(e), "fields": {}}

    def map_to_form_fields(self, ocr_data: dict, form_fields: dict) -> dict:
        """Map OCR-extracted data to form template fields."""
        mapping = {}
        doc_type = ocr_data.get("document_type", "")

        if doc_type == "aadhaar_card":
            field_mapping = {
                "applicant_name": ocr_data.get("name"),
                "mother_name": ocr_data.get("name"),  # If the Aadhaar is of the mother
                "father_name": ocr_data.get("father_name"),
                "address": ocr_data.get("address"),
                "aadhaar_last4": ocr_data.get("aadhaar_last4"),
                "mother_aadhaar": ocr_data.get("aadhaar_last4"),
                "pin_code": ocr_data.get("pin_code"),
                "gender": ocr_data.get("gender"),
                "date_of_birth": ocr_data.get("date_of_birth"),
            }
        elif doc_type == "ration_card":
            field_mapping = {
                "applicant_name": ocr_data.get("head_of_family"),
                "ration_card_type": ocr_data.get("card_type"),
                "ration_card_number": ocr_data.get("card_number"),
                "district": ocr_data.get("district"),
                "mandal": ocr_data.get("mandal"),
                "address": ocr_data.get("address"),
            }
        else:
            fields = ocr_data.get("fields", {})
            field_mapping = {k: v for k, v in fields.items()}

        # Only map fields that exist in the form template
        for form_field in form_fields:
            if form_field in field_mapping and field_mapping[form_field]:
                mapping[form_field] = field_mapping[form_field]

        return mapping

    def _parse_json_response(self, text: str) -> dict:
        """Parse JSON from Claude response, handling markdown code blocks."""
        text = text.strip()
        if text.startswith("```"):
            lines = text.split("\n")
            text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            logger.warning("Failed to parse OCR JSON response")
            return {"fields": {}, "confidence": 0.0}
