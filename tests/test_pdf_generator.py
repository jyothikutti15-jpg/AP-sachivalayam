"""Tests for PDF Generator."""
from unittest.mock import MagicMock

from app.services.pdf_generator import PDFGenerator


class TestHTMLGeneration:
    """Test HTML form generation (the core of PDF rendering)."""

    def _get_generator(self):
        generator = PDFGenerator.__new__(PDFGenerator)
        return generator

    def test_html_includes_ap_header(self):
        gen = self._get_generator()
        template = MagicMock()
        template.name_te = "అమ్మ ఒడి దరఖాస్తు"
        template.name_en = "Amma Vodi Application"
        template.department = "School Education"
        template.gsws_form_code = "GSWS-EDU-AV-01"
        template.fields = {"name": {"label_te": "పేరు", "label_en": "Name", "type": "text"}}

        submission = MagicMock()
        submission.id = "test-uuid-1234"
        submission.field_values = {"name": "రామయ్య"}

        html = gen._build_html(template, submission)

        assert "ఆంధ్రప్రదేశ్ ప్రభుత్వం" in html
        assert "Government of Andhra Pradesh" in html
        assert "School Education" in html
        assert "అమ్మ ఒడి దరఖాస్తు" in html

    def test_html_includes_field_values(self):
        gen = self._get_generator()
        template = MagicMock()
        template.name_te = "Test"
        template.name_en = "Test"
        template.department = "Test Dept"
        template.gsws_form_code = "TEST-01"
        template.fields = {
            "name": {"label_te": "పేరు", "label_en": "Name", "type": "text"},
            "age": {"label_te": "వయస్సు", "label_en": "Age", "type": "number"},
        }

        submission = MagicMock()
        submission.id = "test-uuid"
        submission.field_values = {"name": "రామయ్య", "age": 65}

        html = gen._build_html(template, submission)

        assert "రామయ్య" in html
        assert "65" in html

    def test_html_shows_empty_fields(self):
        gen = self._get_generator()
        template = MagicMock()
        template.name_te = "Test"
        template.name_en = "Test"
        template.department = "Test"
        template.gsws_form_code = "TEST"
        template.fields = {
            "income": {"label_te": "ఆదాయం", "label_en": "Income", "type": "number"},
        }

        submission = MagicMock()
        submission.id = "test"
        submission.field_values = {}  # Empty

        html = gen._build_html(template, submission)
        assert "—" in html  # Empty field placeholder

    def test_html_includes_signature_section(self):
        gen = self._get_generator()
        template = MagicMock()
        template.name_te = "Test"
        template.name_en = "Test"
        template.department = "Test"
        template.gsws_form_code = "TEST"
        template.fields = {}

        submission = MagicMock()
        submission.id = "test"
        submission.field_values = {}

        html = gen._build_html(template, submission)
        assert "దరఖాస్తుదారు సంతకం" in html
        assert "Applicant Signature" in html
        assert "సచివాలయం అధికారి" in html

    def test_html_has_ai_badge(self):
        gen = self._get_generator()
        template = MagicMock()
        template.name_te = "Test"
        template.name_en = "Test"
        template.department = "Test"
        template.gsws_form_code = "TEST"
        template.fields = {}

        submission = MagicMock()
        submission.id = "test"
        submission.field_values = {}

        html = gen._build_html(template, submission)
        assert "AI-Assisted" in html
        assert "AI Copilot" in html

    def test_field_rows_include_both_languages(self):
        gen = self._get_generator()
        rows = gen._build_field_rows(
            {"name": {"label_te": "పేరు", "label_en": "Name", "type": "text"}},
            {"name": "రామయ్య"},
        )
        assert "పేరు" in rows
        assert "Name" in rows
        assert "రామయ్య" in rows
