"""Tests for the Document OCR Service — Aadhaar/ration card extraction."""
import hashlib
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.ocr_service import OCRService


# --- Mock data ---

AADHAAR_JSON = json.dumps({
    "name": "Ramesh Kumar",
    "name_te": "రమేష్ కుమార్",
    "date_of_birth": "15/03/1985",
    "gender": "Male",
    "aadhaar_number": "9876 5432 1098",
    "address": "H.No 4-5, Sachivalayam Street, Guntur, AP",
    "pin_code": "522001",
    "father_name": "Suresh Kumar",
    "confidence": 0.95,
})

RATION_CARD_JSON = json.dumps({
    "card_number": "AP-GNT-2024-001234",
    "card_type": "Rice",
    "head_of_family": "Lakshmi Devi",
    "address": "D.No 2-10, Pedakakani, Guntur, AP",
    "num_members": 4,
    "members": [
        {"name": "Lakshmi Devi", "age": 42, "relation": "Self"},
        {"name": "Ravi Kumar", "age": 45, "relation": "Husband"},
        {"name": "Priya", "age": 18, "relation": "Daughter"},
        {"name": "Anil", "age": 14, "relation": "Son"},
    ],
    "district": "Guntur",
    "mandal": "Pedakakani",
    "confidence": 0.9,
})

GENERIC_DOC_JSON = json.dumps({
    "document_type": "income_certificate",
    "fields": {
        "name": "Suresh Babu",
        "income": "180000",
        "issued_by": "Tahsildar, Guntur",
    },
    "confidence": 0.85,
})

# A fake image (JPEG header)
FAKE_JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 100
# A fake image (PNG header)
FAKE_PNG = b"\x89PNG" + b"\x00" * 100


class TestDocumentDetection:
    """Test document type detection."""

    @pytest.mark.asyncio
    async def test_detect_aadhaar_card(self):
        ocr = OCRService()
        ocr.llm.call_claude_vision = AsyncMock(return_value="aadhaar_card")
        result = await ocr.detect_document_type(FAKE_JPEG)
        assert result == "aadhaar_card"

    @pytest.mark.asyncio
    async def test_detect_ration_card(self):
        ocr = OCRService()
        ocr.llm.call_claude_vision = AsyncMock(return_value="ration_card")
        result = await ocr.detect_document_type(FAKE_JPEG)
        assert result == "ration_card"

    @pytest.mark.asyncio
    async def test_detect_other_document(self):
        ocr = OCRService()
        ocr.llm.call_claude_vision = AsyncMock(return_value="income_certificate")
        result = await ocr.detect_document_type(FAKE_JPEG)
        assert result == "income_certificate"

    @pytest.mark.asyncio
    async def test_detect_not_a_document(self):
        ocr = OCRService()
        ocr.llm.call_claude_vision = AsyncMock(return_value="not_a_document")
        result = await ocr.detect_document_type(FAKE_JPEG)
        assert result == "not_a_document"

    @pytest.mark.asyncio
    async def test_detect_unknown_returns_other(self):
        ocr = OCRService()
        ocr.llm.call_claude_vision = AsyncMock(return_value="random_garbage_type")
        result = await ocr.detect_document_type(FAKE_JPEG)
        assert result == "other"

    @pytest.mark.asyncio
    async def test_detect_normalizes_whitespace(self):
        ocr = OCRService()
        ocr.llm.call_claude_vision = AsyncMock(return_value="  Aadhaar Card  ")
        result = await ocr.detect_document_type(FAKE_JPEG)
        assert result == "aadhaar_card"

    @pytest.mark.asyncio
    async def test_detect_handles_exception(self):
        ocr = OCRService()
        ocr.llm.call_claude_vision = AsyncMock(side_effect=Exception("API error"))
        result = await ocr.detect_document_type(FAKE_JPEG)
        assert result == "other"


class TestAadhaarExtraction:
    """Test Aadhaar card field extraction."""

    @pytest.mark.asyncio
    async def test_extract_aadhaar_fields(self):
        ocr = OCRService()
        # First call: detect type, second call: extract fields
        ocr.llm.call_claude_vision = AsyncMock(side_effect=["aadhaar_card", AADHAAR_JSON])
        result = await ocr.extract_document_fields(FAKE_JPEG)

        assert result["document_type"] == "aadhaar_card"
        assert result["name"] == "Ramesh Kumar"
        assert result["name_te"] == "రమేష్ కుమార్"
        assert result["date_of_birth"] == "15/03/1985"
        assert result["gender"] == "Male"
        assert result["father_name"] == "Suresh Kumar"
        assert result["pin_code"] == "522001"

    @pytest.mark.asyncio
    async def test_extract_aadhaar_with_known_type(self):
        ocr = OCRService()
        ocr.llm.call_claude_vision = AsyncMock(return_value=AADHAAR_JSON)
        result = await ocr.extract_document_fields(FAKE_JPEG, document_type="aadhaar_card")

        assert result["document_type"] == "aadhaar_card"
        assert result["name"] == "Ramesh Kumar"
        # Should only call vision once (no detection needed)
        assert ocr.llm.call_claude_vision.call_count == 1

    @pytest.mark.asyncio
    async def test_aadhaar_masking(self):
        ocr = OCRService()
        ocr.llm.call_claude_vision = AsyncMock(return_value=AADHAAR_JSON)
        result = await ocr.extract_document_fields(FAKE_JPEG, document_type="aadhaar_card")

        # Raw Aadhaar should be masked
        assert result["aadhaar_number"] == "XXXX XXXX 1098"
        assert result["aadhaar_last4"] == "1098"

    @pytest.mark.asyncio
    async def test_aadhaar_hashing(self):
        ocr = OCRService()
        ocr.llm.call_claude_vision = AsyncMock(return_value=AADHAAR_JSON)
        result = await ocr.extract_document_fields(FAKE_JPEG, document_type="aadhaar_card")

        expected_hash = hashlib.sha256("987654321098".encode()).hexdigest()
        assert result["aadhaar_hash"] == expected_hash

    @pytest.mark.asyncio
    async def test_extraction_error_returns_error_dict(self):
        ocr = OCRService()
        ocr.llm.call_claude_vision = AsyncMock(side_effect=Exception("Vision API down"))
        result = await ocr.extract_document_fields(FAKE_JPEG, document_type="aadhaar_card")

        assert result["document_type"] == "aadhaar_card"
        assert "error" in result


class TestRationCardExtraction:
    """Test ration card field extraction."""

    @pytest.mark.asyncio
    async def test_extract_ration_card_fields(self):
        ocr = OCRService()
        ocr.llm.call_claude_vision = AsyncMock(return_value=RATION_CARD_JSON)
        result = await ocr.extract_document_fields(FAKE_JPEG, document_type="ration_card")

        assert result["document_type"] == "ration_card"
        assert result["card_number"] == "AP-GNT-2024-001234"
        assert result["card_type"] == "Rice"
        assert result["head_of_family"] == "Lakshmi Devi"
        assert result["district"] == "Guntur"
        assert result["mandal"] == "Pedakakani"
        assert result["num_members"] == 4
        assert len(result["members"]) == 4

    @pytest.mark.asyncio
    async def test_ration_card_no_aadhaar_fields(self):
        ocr = OCRService()
        ocr.llm.call_claude_vision = AsyncMock(return_value=RATION_CARD_JSON)
        result = await ocr.extract_document_fields(FAKE_JPEG, document_type="ration_card")

        # Ration card should not have Aadhaar-specific fields
        assert "aadhaar_hash" not in result
        assert "aadhaar_last4" not in result


class TestFormFieldMapping:
    """Test OCR data to form field mapping."""

    def test_aadhaar_to_form_mapping(self):
        ocr = OCRService()
        ocr_data = {
            "document_type": "aadhaar_card",
            "name": "Ramesh Kumar",
            "father_name": "Suresh Kumar",
            "address": "Guntur, AP",
            "aadhaar_last4": "1098",
            "pin_code": "522001",
            "gender": "Male",
            "date_of_birth": "15/03/1985",
        }
        form_fields = {
            "applicant_name": {"type": "text", "required": True},
            "father_name": {"type": "text", "required": True},
            "address": {"type": "text", "required": True},
            "pin_code": {"type": "text"},
            "gender": {"type": "select"},
            "annual_income": {"type": "number"},  # Not in OCR data
        }
        mapping = ocr.map_to_form_fields(ocr_data, form_fields)

        assert mapping["applicant_name"] == "Ramesh Kumar"
        assert mapping["father_name"] == "Suresh Kumar"
        assert mapping["address"] == "Guntur, AP"
        assert mapping["pin_code"] == "522001"
        assert mapping["gender"] == "Male"
        assert "annual_income" not in mapping  # Not available from Aadhaar

    def test_ration_card_to_form_mapping(self):
        ocr = OCRService()
        ocr_data = {
            "document_type": "ration_card",
            "head_of_family": "Lakshmi Devi",
            "card_type": "Rice",
            "card_number": "AP-GNT-001234",
            "district": "Guntur",
            "mandal": "Pedakakani",
            "address": "Pedakakani, Guntur",
        }
        form_fields = {
            "applicant_name": {"type": "text", "required": True},
            "ration_card_type": {"type": "select"},
            "ration_card_number": {"type": "text"},
            "district": {"type": "text"},
            "mandal": {"type": "text"},
        }
        mapping = ocr.map_to_form_fields(ocr_data, form_fields)

        assert mapping["applicant_name"] == "Lakshmi Devi"
        assert mapping["ration_card_type"] == "Rice"
        assert mapping["ration_card_number"] == "AP-GNT-001234"
        assert mapping["district"] == "Guntur"
        assert mapping["mandal"] == "Pedakakani"

    def test_generic_document_to_form_mapping(self):
        ocr = OCRService()
        ocr_data = {
            "document_type": "income_certificate",
            "fields": {
                "name": "Suresh Babu",
                "income": "180000",
            },
        }
        form_fields = {
            "name": {"type": "text"},
            "income": {"type": "number"},
            "age": {"type": "number"},  # Not in OCR data
        }
        mapping = ocr.map_to_form_fields(ocr_data, form_fields)

        assert mapping["name"] == "Suresh Babu"
        assert mapping["income"] == "180000"
        assert "age" not in mapping

    def test_mapping_skips_none_values(self):
        ocr = OCRService()
        ocr_data = {
            "document_type": "aadhaar_card",
            "name": "Ramesh",
            "father_name": None,  # Not visible on card
            "address": "Guntur",
        }
        form_fields = {
            "applicant_name": {"type": "text"},
            "father_name": {"type": "text"},
            "address": {"type": "text"},
        }
        mapping = ocr.map_to_form_fields(ocr_data, form_fields)

        assert mapping["applicant_name"] == "Ramesh"
        assert "father_name" not in mapping  # None values should be skipped
        assert mapping["address"] == "Guntur"

    def test_mapping_only_includes_form_fields(self):
        ocr = OCRService()
        ocr_data = {
            "document_type": "aadhaar_card",
            "name": "Ramesh",
            "address": "Guntur",
            "aadhaar_last4": "1098",
        }
        # Form only has one matching field
        form_fields = {
            "applicant_name": {"type": "text"},
        }
        mapping = ocr.map_to_form_fields(ocr_data, form_fields)

        assert mapping == {"applicant_name": "Ramesh"}


class TestJSONParsing:
    """Test JSON response parsing from Claude."""

    def test_parse_clean_json(self):
        ocr = OCRService()
        text = '{"name": "Ramesh", "age": 35}'
        result = ocr._parse_json_response(text)
        assert result == {"name": "Ramesh", "age": 35}

    def test_parse_markdown_wrapped_json(self):
        ocr = OCRService()
        text = '```json\n{"name": "Ramesh", "age": 35}\n```'
        result = ocr._parse_json_response(text)
        assert result == {"name": "Ramesh", "age": 35}

    def test_parse_markdown_no_language_tag(self):
        ocr = OCRService()
        text = '```\n{"name": "Ramesh"}\n```'
        result = ocr._parse_json_response(text)
        assert result == {"name": "Ramesh"}

    def test_parse_invalid_json(self):
        ocr = OCRService()
        text = "This is not JSON at all"
        result = ocr._parse_json_response(text)
        assert result == {"fields": {}, "confidence": 0.0}

    def test_parse_json_with_whitespace(self):
        ocr = OCRService()
        text = '  \n  {"name": "Ramesh"}  \n  '
        result = ocr._parse_json_response(text)
        assert result == {"name": "Ramesh"}

    def test_parse_complex_aadhaar_json(self):
        ocr = OCRService()
        result = ocr._parse_json_response(AADHAAR_JSON)
        assert result["name"] == "Ramesh Kumar"
        assert result["confidence"] == 0.95


class TestPIIProtection:
    """Verify Aadhaar is never stored raw."""

    @pytest.mark.asyncio
    async def test_raw_aadhaar_never_in_result(self):
        ocr = OCRService()
        ocr.llm.call_claude_vision = AsyncMock(return_value=AADHAAR_JSON)
        result = await ocr.extract_document_fields(FAKE_JPEG, document_type="aadhaar_card")

        # The raw 12-digit number should NOT appear
        raw_number = "987654321098"
        result_str = json.dumps(result)
        assert raw_number not in result_str

    @pytest.mark.asyncio
    async def test_aadhaar_hash_is_sha256(self):
        ocr = OCRService()
        ocr.llm.call_claude_vision = AsyncMock(return_value=AADHAAR_JSON)
        result = await ocr.extract_document_fields(FAKE_JPEG, document_type="aadhaar_card")

        # Hash should be valid SHA-256 (64 hex characters)
        assert len(result["aadhaar_hash"]) == 64
        assert all(c in "0123456789abcdef" for c in result["aadhaar_hash"])

    @pytest.mark.asyncio
    async def test_aadhaar_last4_is_correct(self):
        ocr = OCRService()
        ocr.llm.call_claude_vision = AsyncMock(return_value=AADHAAR_JSON)
        result = await ocr.extract_document_fields(FAKE_JPEG, document_type="aadhaar_card")

        assert result["aadhaar_last4"] == "1098"

    @pytest.mark.asyncio
    async def test_masked_aadhaar_format(self):
        ocr = OCRService()
        ocr.llm.call_claude_vision = AsyncMock(return_value=AADHAAR_JSON)
        result = await ocr.extract_document_fields(FAKE_JPEG, document_type="aadhaar_card")

        assert result["aadhaar_number"] == "XXXX XXXX 1098"

    @pytest.mark.asyncio
    async def test_invalid_aadhaar_not_hashed(self):
        """If Aadhaar is not 12 digits, don't hash/mask."""
        invalid_json = json.dumps({
            "name": "Test",
            "aadhaar_number": "1234 5678",  # Only 8 digits
            "confidence": 0.5,
        })
        ocr = OCRService()
        ocr.llm.call_claude_vision = AsyncMock(return_value=invalid_json)
        result = await ocr.extract_document_fields(FAKE_JPEG, document_type="aadhaar_card")

        assert "aadhaar_hash" not in result
        assert "aadhaar_last4" not in result
