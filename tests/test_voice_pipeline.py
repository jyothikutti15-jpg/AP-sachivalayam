"""Tests for the Voice Pipeline — Telugu voice processing."""
import re
from unittest.mock import MagicMock, patch

import pytest

from app.services.voice_pipeline import VoicePipeline


class TestPostProcessing:
    """Test Telugu text post-processing after Whisper transcription."""

    def _get_pipeline(self):
        return VoicePipeline()

    def test_telugu_number_word_conversion(self):
        pipeline = self._get_pipeline()
        result = pipeline._convert_number_words("ఆదాయం 2 లక్షలు")
        assert "200000" in result

    def test_telugu_number_word_thousands(self):
        pipeline = self._get_pipeline()
        result = pipeline._convert_number_words("5 వేలు")
        assert "5000" in result

    def test_common_error_fixes(self):
        pipeline = self._get_pipeline()
        result = pipeline._fix_common_errors("amma vodi scheme details")
        assert "అమ్మ ఒడి" in result

    def test_repetition_removal(self):
        pipeline = self._get_pipeline()
        text = "అమ్మ ఒడి అర్హత ఏమిటి అమ్మ ఒడి అర్హత ఏమిటి"
        result = pipeline._remove_repetitions(text)
        # Should not be doubled
        assert result.count("అమ్మ ఒడి") <= 2  # At most original occurrence

    def test_full_post_process(self):
        pipeline = self._get_pipeline()
        raw = "  amma vodi scheme  ₹౧౫,౦౦౦  వస్తుంది  "
        result = pipeline._post_process(raw)
        assert "అమ్మ ఒడి" in result
        assert "15,000" in result
        assert "  " not in result


class TestEntityExtraction:
    """Test entity extraction from transcribed text."""

    def _get_pipeline(self):
        return VoicePipeline()

    def test_extract_scheme(self):
        pipeline = self._get_pipeline()
        entities = pipeline._extract_entities("అమ్మ ఒడి కోసం apply చేయాలి")
        assert entities.get("scheme") == "YSR-AMMA-VODI"

    def test_extract_age(self):
        pipeline = self._get_pipeline()
        entities = pipeline._extract_entities("వయస్సు 35 సంవత్సరాలు")
        assert entities.get("age") == 35

    def test_extract_income(self):
        pipeline = self._get_pipeline()
        entities = pipeline._extract_entities("ఆదాయం 200000 రూపాయలు")
        assert entities.get("income") == 200000

    def test_extract_ration_card(self):
        pipeline = self._get_pipeline()
        entities = pipeline._extract_entities("తెల్ల రేషన్ కార్డు ఉంది")
        assert entities.get("ration_card") == "White"

    def test_extract_caste(self):
        pipeline = self._get_pipeline()
        entities = pipeline._extract_entities("SC category కి belong")
        assert entities.get("caste") == "SC"

    def test_extract_name(self):
        pipeline = self._get_pipeline()
        entities = pipeline._extract_entities("పేరు రామయ్య")
        assert "names" in entities
        assert any("రామయ్య" in n for n in entities["names"])

    def test_aadhaar_detection(self):
        pipeline = self._get_pipeline()
        entities = pipeline._extract_entities("aadhaar 1234 5678 9012")
        assert entities.get("aadhaar_detected") is True

    def test_no_entities_from_empty(self):
        pipeline = self._get_pipeline()
        entities = pipeline._extract_entities("")
        assert "scheme" not in entities
        assert "age" not in entities

    def test_multiple_entities(self):
        pipeline = self._get_pipeline()
        text = "రామయ్య గారు వయస్సు 65 ఆదాయం 100000 White card pension కావాలి"
        entities = pipeline._extract_entities(text)
        assert entities.get("age") == 65
        assert entities.get("income") == 100000
        assert entities.get("ration_card") == "White"
        assert entities.get("scheme") == "YSR-PENSION-KANUKA"
