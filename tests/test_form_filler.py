"""Tests for Form Filler — auto-filling government forms from text/voice."""
import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest


class TestFormTemplates:
    """Test form template data integrity."""

    def test_all_templates_valid_json(self):
        templates_file = Path(__file__).parent.parent / "app" / "data" / "templates" / "form_templates.json"
        with open(templates_file, encoding="utf-8") as f:
            templates = json.load(f)

        assert isinstance(templates, list)
        assert len(templates) >= 10, f"Expected 10+ templates, got {len(templates)}"

    def test_each_template_has_required_keys(self):
        templates_file = Path(__file__).parent.parent / "app" / "data" / "templates" / "form_templates.json"
        with open(templates_file, encoding="utf-8") as f:
            templates = json.load(f)

        for t in templates:
            assert "name_te" in t, f"Missing name_te"
            assert "name_en" in t, f"Missing name_en"
            assert "fields" in t, f"Missing fields in {t['name_en']}"
            assert "scheme_code" in t, f"Missing scheme_code in {t['name_en']}"
            assert len(t["fields"]) >= 5, f"Too few fields in {t['name_en']}"

    def test_each_field_has_labels(self):
        templates_file = Path(__file__).parent.parent / "app" / "data" / "templates" / "form_templates.json"
        with open(templates_file, encoding="utf-8") as f:
            templates = json.load(f)

        for t in templates:
            for field_name, defn in t["fields"].items():
                assert "label_te" in defn, f"Missing label_te for {field_name} in {t['name_en']}"
                assert "label_en" in defn, f"Missing label_en for {field_name} in {t['name_en']}"
                assert "type" in defn, f"Missing type for {field_name} in {t['name_en']}"

    def test_aadhaar_fields_use_last4_type(self):
        """Aadhaar fields should use aadhaar_last4 type for security."""
        templates_file = Path(__file__).parent.parent / "app" / "data" / "templates" / "form_templates.json"
        with open(templates_file, encoding="utf-8") as f:
            templates = json.load(f)

        for t in templates:
            for field_name, defn in t["fields"].items():
                if "aadhaar" in field_name.lower():
                    assert defn["type"] == "aadhaar_last4", \
                        f"Aadhaar field {field_name} in {t['name_en']} should use type 'aadhaar_last4'"


class TestFormFieldsDescription:
    """Test form fields description building."""

    def test_build_fields_description(self):
        from app.services.form_filler import FormFiller

        filler = FormFiller.__new__(FormFiller)
        fields = {
            "name": {"label_te": "పేరు", "label_en": "Name", "type": "text", "required": True},
            "age": {"label_te": "వయస్సు", "label_en": "Age", "type": "number", "required": True},
            "caste": {"label_te": "కులం", "label_en": "Caste", "type": "select", "options": ["SC", "ST", "BC"], "required": True},
        }

        result = filler._build_fields_description(fields)
        assert "పేరు" in result
        assert "REQUIRED" in result
        assert "SC, ST, BC" in result

    def test_find_name_field(self):
        from app.services.form_filler import FormFiller

        filler = FormFiller.__new__(FormFiller)
        assert filler._find_name_field({"applicant_name": {}, "age": {}}) == "applicant_name"
        assert filler._find_name_field({"mother_name": {}, "age": {}}) == "mother_name"
        assert filler._find_name_field({"farmer_name": {}, "survey": {}}) == "farmer_name"


class TestVoiceEntityApplication:
    """Test applying voice entities to form fields."""

    def test_apply_age_entity(self):
        from app.services.form_filler import FormFiller

        filler = FormFiller.__new__(FormFiller)
        field_values = {}
        confidence = {}
        entities = {"age": 65}
        template_fields = {"age": {"type": "number"}}

        result_values, result_conf = filler._apply_voice_entities(
            field_values, confidence, entities, template_fields
        )
        assert result_values["age"] == 65
        assert result_conf["age"] == 0.7

    def test_apply_income_entity(self):
        from app.services.form_filler import FormFiller

        filler = FormFiller.__new__(FormFiller)
        field_values = {}
        confidence = {}
        entities = {"income": 200000}
        template_fields = {"annual_income": {"type": "number"}}

        result_values, _ = filler._apply_voice_entities(
            field_values, confidence, entities, template_fields
        )
        assert result_values["annual_income"] == 200000

    def test_doesnt_override_existing_values(self):
        from app.services.form_filler import FormFiller

        filler = FormFiller.__new__(FormFiller)
        field_values = {"age": 70}
        confidence = {"age": 1.0}
        entities = {"age": 65}
        template_fields = {"age": {"type": "number"}}

        result_values, result_conf = filler._apply_voice_entities(
            field_values, confidence, entities, template_fields
        )
        assert result_values["age"] == 70  # Should keep existing
        assert result_conf["age"] == 1.0


class TestExtractionParsing:
    """Test Claude response parsing."""

    def test_parse_valid_json(self):
        from app.services.form_filler import FormFiller

        filler = FormFiller.__new__(FormFiller)
        response = json.dumps({
            "field_values": {"name": "రామయ్య", "age": 65},
            "confidence_scores": {"name": 0.9, "age": 0.8},
            "missing_fields": ["income"]
        })

        values, scores, missing = filler._parse_extraction(response, {})
        assert values["name"] == "రామయ్య"
        assert scores["age"] == 0.8
        assert "income" in missing

    def test_parse_markdown_wrapped_json(self):
        from app.services.form_filler import FormFiller

        filler = FormFiller.__new__(FormFiller)
        response = '```json\n{"field_values": {"name": "test"}, "confidence_scores": {}, "missing_fields": []}\n```'

        values, _, _ = filler._parse_extraction(response, {})
        assert values["name"] == "test"

    def test_parse_invalid_returns_all_missing(self):
        from app.services.form_filler import FormFiller

        filler = FormFiller.__new__(FormFiller)
        fields = {
            "name": {"required": True},
            "age": {"required": True},
            "hobby": {"required": False},
        }

        values, scores, missing = filler._parse_extraction("not json", fields)
        assert values == {}
        assert "name" in missing
        assert "age" in missing
        assert "hobby" not in missing  # Not required


class TestConfirmationMessage:
    """Test confirmation message generation."""

    def test_message_includes_field_values(self):
        from app.services.form_filler import FormFiller

        filler = FormFiller.__new__(FormFiller)
        template = MagicMock()
        template.name_te = "అమ్మ ఒడి దరఖాస్తు"
        template.fields = {
            "name": {"label_te": "పేరు", "label_en": "Name", "type": "text", "required": True},
        }

        msg = filler._build_confirmation_message(
            template,
            {"name": "రామయ్య"},
            {"name": 0.9},
            [],
        )
        assert "రామయ్య" in msg
        assert "✅" in msg  # High confidence

    def test_message_shows_missing_fields(self):
        from app.services.form_filler import FormFiller

        filler = FormFiller.__new__(FormFiller)
        template = MagicMock()
        template.name_te = "Test"
        template.fields = {
            "income": {"label_te": "ఆదాయం", "label_en": "Income", "type": "number", "required": True},
        }

        msg = filler._build_confirmation_message(template, {}, {}, ["income"])
        assert "❌" in msg
        assert "ఆదాయం" in msg
