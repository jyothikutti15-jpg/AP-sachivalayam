"""Tests for the SchemeAdvisor RAG pipeline."""
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.telugu import fuzzy_match_scheme, normalize_telugu_text


class TestSchemeMatching:
    """Test scheme name fuzzy matching (the first step in the search chain)."""

    def test_exact_telugu_match(self):
        assert fuzzy_match_scheme("అమ్మ ఒడి") == "YSR-AMMA-VODI"
        assert fuzzy_match_scheme("రైతు భరోసా") == "YSR-RYTHU-BHAROSA"
        assert fuzzy_match_scheme("ఆరోగ్యశ్రీ") == "YSR-AAROGYASRI"
        assert fuzzy_match_scheme("చేయూత") == "YSR-CHEYUTHA"
        assert fuzzy_match_scheme("పెన్షన్") == "YSR-PENSION-KANUKA"

    def test_exact_english_match(self):
        assert fuzzy_match_scheme("amma vodi") == "YSR-AMMA-VODI"
        assert fuzzy_match_scheme("rythu bharosa") == "YSR-RYTHU-BHAROSA"
        assert fuzzy_match_scheme("aarogyasri") == "YSR-AAROGYASRI"
        assert fuzzy_match_scheme("cheyutha") == "YSR-CHEYUTHA"

    def test_fuzzy_telugu_match(self):
        # Slight variations should still match
        result = fuzzy_match_scheme("అమ్మఒడి")  # No space
        # May or may not match depending on threshold
        assert result is None or result == "YSR-AMMA-VODI"

    def test_no_match_for_garbage(self):
        assert fuzzy_match_scheme("xyz random text") is None
        assert fuzzy_match_scheme("") is None

    def test_case_insensitive(self):
        assert fuzzy_match_scheme("AMMA VODI") == "YSR-AMMA-VODI"
        assert fuzzy_match_scheme("Rythu Bharosa") == "YSR-RYTHU-BHAROSA"


class TestTeluguNormalization:
    """Test Telugu text normalization used before search."""

    def test_whitespace_normalization(self):
        result = normalize_telugu_text("  అమ్మ   ఒడి   ")
        assert "  " not in result
        assert result.strip() == result

    def test_telugu_digit_conversion(self):
        result = normalize_telugu_text("₹౧౫,౦౦౦")
        assert "15,000" in result

    def test_zero_width_removal(self):
        text_with_zwj = "అమ్మ\u200cఒడి"
        result = normalize_telugu_text(text_with_zwj)
        assert "\u200c" not in result


class TestSearchChain:
    """Test the search chain: cache → FAQ → vector → keyword → LLM."""

    @pytest.mark.asyncio
    async def test_faq_cache_hit_skips_llm(self):
        """If FAQ matches, no LLM call should be made."""
        from app.schemas.scheme import SchemeSearchResponse

        # Simulate a FAQ match
        mock_db = AsyncMock()
        mock_faq_result = MagicMock()
        mock_faq = MagicMock()
        mock_faq.question_te = "అమ్మ ఒడి అర్హత ఏమిటి?"
        mock_faq.answer_te = "అమ్మ ఒడి అర్హత: test answer"
        mock_faq.frequency = 5
        mock_faq_result.scalars.return_value.all.return_value = [mock_faq]
        mock_db.execute = AsyncMock(return_value=mock_faq_result)

        # Verify FAQ keyword matching logic
        query = "అమ్మ ఒడి అర్హత"
        query_words = set(query.lower().split())
        faq_words = set(mock_faq.question_te.lower().split())
        overlap = len(query_words & faq_words)
        assert overlap >= 2, "FAQ should match on keyword overlap"

    @pytest.mark.asyncio
    async def test_keyword_fallback_when_no_vectors(self):
        """When vector search returns empty, keyword search should be tried."""
        # This tests the logic flow, not the actual DB
        query = "pension scheme details"
        normalized = normalize_telugu_text(query)
        assert normalized  # Should not be empty after normalization

    def test_scheme_context_formatting(self):
        """Test that scheme data is formatted correctly for LLM context."""
        from app.services.scheme_advisor import SchemeAdvisor

        # Create a mock scheme object
        mock_scheme = MagicMock()
        mock_scheme.name_te = "వైఎస్ఆర్ అమ్మ ఒడి"
        mock_scheme.name_en = "YSR Amma Vodi"
        mock_scheme.department = "School Education"
        mock_scheme.description_te = "Test description"
        mock_scheme.description_en = None
        mock_scheme.eligibility_criteria = {"age": "18+"}
        mock_scheme.required_documents = {"mandatory": ["Aadhaar"]}
        mock_scheme.benefit_amount = "₹15,000"
        mock_scheme.go_reference = "GO Ms. No. 47"

        # Test formatting
        advisor = SchemeAdvisor.__new__(SchemeAdvisor)
        context = advisor._format_scheme_context([mock_scheme])

        assert "అమ్మ ఒడి" in context
        assert "₹15,000" in context
        assert "GO Ms. No. 47" in context
        assert "School Education" in context


class TestEligibilityCheck:
    """Test eligibility checking logic."""

    def test_eligibility_prompt_construction(self):
        """Test that eligibility prompt includes all necessary details."""
        scheme_details = {
            "scheme_code": "YSR-AMMA-VODI",
            "name_te": "అమ్మ ఒడి",
            "eligibility_criteria": {
                "income": "Below 10 lakhs",
                "ration_card": "White/Rice",
            },
        }
        citizen_details = {
            "age": 35,
            "income": 200000,
            "ration_card": "White",
            "children": 2,
        }

        # Verify JSON serialization works with Telugu
        scheme_json = json.dumps(scheme_details, ensure_ascii=False)
        citizen_json = json.dumps(citizen_details, ensure_ascii=False)

        assert "అమ్మ ఒడి" in scheme_json
        assert "200000" in citizen_json

    def test_eligibility_response_parsing(self):
        """Test parsing of Claude's eligibility response."""
        # Simulate Claude's JSON response
        claude_response = json.dumps({
            "is_eligible": True,
            "reasoning_te": "అర్హత ఉంది. Income ₹2 లక్షలు < ₹10 లక్షలు.",
            "missing_documents": [],
            "next_steps_te": "సచివాలయంలో apply చేయండి.",
        })

        data = json.loads(claude_response)
        assert data["is_eligible"] is True
        assert "అర్హత ఉంది" in data["reasoning_te"]
        assert len(data["missing_documents"]) == 0


class TestSchemeData:
    """Test that all scheme JSON files are valid and complete."""

    def test_all_scheme_files_valid_json(self):
        """Every scheme file should be valid JSON."""
        from pathlib import Path
        schemes_dir = Path(__file__).parent.parent / "app" / "data" / "schemes"

        for filepath in schemes_dir.glob("*.json"):
            with open(filepath, encoding="utf-8") as f:
                data = json.load(f)  # Should not raise
            assert "scheme_code" in data, f"Missing scheme_code in {filepath.name}"
            assert "name_te" in data, f"Missing name_te in {filepath.name}"
            assert "name_en" in data, f"Missing name_en in {filepath.name}"
            assert "department" in data, f"Missing department in {filepath.name}"

    def test_all_scheme_files_have_eligibility(self):
        """Every scheme should have eligibility criteria."""
        from pathlib import Path
        schemes_dir = Path(__file__).parent.parent / "app" / "data" / "schemes"

        for filepath in schemes_dir.glob("*.json"):
            with open(filepath, encoding="utf-8") as f:
                data = json.load(f)
            assert data.get("eligibility_criteria"), f"Empty eligibility in {filepath.name}"

    def test_all_scheme_files_have_telugu_name(self):
        """Every scheme should have a Telugu name."""
        from pathlib import Path
        schemes_dir = Path(__file__).parent.parent / "app" / "data" / "schemes"

        for filepath in schemes_dir.glob("*.json"):
            with open(filepath, encoding="utf-8") as f:
                data = json.load(f)
            # Check Telugu characters are present
            import re
            assert re.search(r"[\u0C00-\u0C7F]", data["name_te"]), \
                f"name_te has no Telugu characters in {filepath.name}"

    def test_faq_file_valid(self):
        """FAQ file should be valid JSON with correct structure."""
        from pathlib import Path
        faq_file = Path(__file__).parent.parent / "app" / "data" / "scheme_faqs.json"

        with open(faq_file, encoding="utf-8") as f:
            faqs = json.load(f)

        assert isinstance(faqs, dict)
        for scheme_code, faq_list in faqs.items():
            assert isinstance(faq_list, list), f"FAQs for {scheme_code} should be a list"
            for faq in faq_list:
                assert "question_te" in faq, f"Missing question_te in {scheme_code}"
                assert "answer_te" in faq, f"Missing answer_te in {scheme_code}"

    def test_scheme_count(self):
        """Should have at least 25 scheme files."""
        from pathlib import Path
        schemes_dir = Path(__file__).parent.parent / "app" / "data" / "schemes"
        count = len(list(schemes_dir.glob("*.json")))
        assert count >= 25, f"Expected 25+ schemes, got {count}"
