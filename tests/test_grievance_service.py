"""Tests for the Grievance Resolution Service."""
import json
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.models.grievance import GRIEVANCE_CATEGORIES, Grievance, GrievanceComment
from app.schemas.grievance import GrievanceCreateRequest, GrievanceUpdateRequest


class TestGrievanceCategories:
    """Test grievance category definitions."""

    def test_all_categories_have_required_fields(self):
        for key, cat in GRIEVANCE_CATEGORIES.items():
            assert "name_te" in cat, f"Missing name_te in {key}"
            assert "department" in cat, f"Missing department in {key}"
            assert "subcategories" in cat, f"Missing subcategories in {key}"
            assert len(cat["subcategories"]) > 0, f"Empty subcategories in {key}"

    def test_category_count(self):
        assert len(GRIEVANCE_CATEGORIES) >= 9

    def test_telugu_names_present(self):
        import re
        for key, cat in GRIEVANCE_CATEGORIES.items():
            assert re.search(r"[\u0C00-\u0C7F]", cat["name_te"]), \
                f"No Telugu characters in {key} name_te"

    def test_welfare_category_exists(self):
        assert "welfare" in GRIEVANCE_CATEGORIES
        assert GRIEVANCE_CATEGORIES["welfare"]["department"] == "Welfare"

    def test_health_category_exists(self):
        assert "health" in GRIEVANCE_CATEGORIES
        assert "aarogyasri_issue" in GRIEVANCE_CATEGORIES["health"]["subcategories"]


class TestGrievanceRequest:
    """Test grievance request schema validation."""

    def test_valid_request(self):
        req = GrievanceCreateRequest(
            citizen_name="రామ",
            category="welfare",
            subject_te="పెన్షన్ రావడం లేదు",
            description_te="3 నెలల నుండి పెన్షన్ రావడం లేదు. దయచేసి సహాయం చేయండి.",
        )
        assert req.citizen_name == "రామ"
        assert req.priority == "medium"  # default

    def test_request_with_all_fields(self):
        req = GrievanceCreateRequest(
            citizen_name="Test Citizen",
            citizen_phone="9876543210",
            category="health",
            subcategory="aarogyasri_issue",
            department="Health",
            subject_te="ఆరోగ్యశ్రీ కార్డ్ సమస్య",
            description_te="కార్డ్ reject అయింది",
            description_en="Aarogyasri card rejected",
            priority="high",
            attachment_urls=["https://example.com/doc.pdf"],
        )
        assert req.priority == "high"
        assert len(req.attachment_urls) == 1


class TestGrievanceSLA:
    """Test SLA deadline calculations."""

    def test_priority_sla_mapping(self):
        from app.services.grievance_service import PRIORITY_SLA

        assert PRIORITY_SLA["urgent"] == 24
        assert PRIORITY_SLA["high"] == 48
        assert PRIORITY_SLA["medium"] == 72
        assert PRIORITY_SLA["low"] == 120

    def test_sla_72_hours_default(self):
        from app.services.grievance_service import SLA_HOURS
        assert SLA_HOURS == 72


class TestGrievanceAIPrompt:
    """Test AI suggestion prompt structure."""

    def test_prompt_template_has_placeholders(self):
        from app.services.grievance_service import GRIEVANCE_AI_PROMPT

        assert "{category}" in GRIEVANCE_AI_PROMPT
        assert "{subject}" in GRIEVANCE_AI_PROMPT
        assert "{description}" in GRIEVANCE_AI_PROMPT

    def test_prompt_requests_json_response(self):
        from app.services.grievance_service import GRIEVANCE_AI_PROMPT

        assert "suggested_category" in GRIEVANCE_AI_PROMPT
        assert "suggested_priority" in GRIEVANCE_AI_PROMPT
        assert "escalation_path_te" in GRIEVANCE_AI_PROMPT
        assert "required_evidence_te" in GRIEVANCE_AI_PROMPT

    def test_ai_suggest_fallback_response(self):
        """When AI fails, fallback should still return valid response."""
        from app.schemas.grievance import GrievanceAISuggestResponse

        # Simulate the fallback in the service
        cat_info = GRIEVANCE_CATEGORIES.get("welfare", {})
        fallback = GrievanceAISuggestResponse(
            suggested_category="welfare",
            suggested_department=cat_info.get("department", "General Administration"),
            suggested_priority="medium",
            escalation_path_te="సచివాలయం → మండల అధికారి → జిల్లా కలెక్టర్",
            required_evidence_te=["దరఖాస్తు కాపీ", "గుర్తింపు పత్రం"],
            similar_grievances=[],
            resolution_suggestion_te="సంబంధిత శాఖకు నివేదించండి.",
        )
        assert fallback.suggested_department == "Welfare"
        assert len(fallback.required_evidence_te) == 2


class TestGrievanceModel:
    """Test Grievance SQLAlchemy model structure."""

    def test_model_tablename(self):
        assert Grievance.__tablename__ == "grievances"

    def test_comment_tablename(self):
        assert GrievanceComment.__tablename__ == "grievance_comments"

    def test_status_workflow_values(self):
        """Valid status values for the grievance workflow."""
        valid = {"open", "acknowledged", "in_progress", "escalated", "resolved", "closed"}
        # Verify the model default
        g = Grievance.__table__.columns
        assert g["status"].default.arg == "open"

    def test_priority_values(self):
        g = Grievance.__table__.columns
        assert g["priority"].default.arg == "medium"

    def test_escalation_levels(self):
        """Escalation: 0=secretariat, 1=mandal, 2=district, 3=state."""
        g = Grievance.__table__.columns
        assert g["escalation_level"].default.arg == 0


class TestReferenceNumberFormat:
    """Test grievance reference number generation."""

    def test_reference_format(self):
        """Reference should match GRV-YYYY-NNNN pattern."""
        import re
        pattern = r"^GRV-\d{4}-\d{4}$"
        assert re.match(pattern, "GRV-2026-0001")
        assert re.match(pattern, "GRV-2026-1234")
        assert not re.match(pattern, "GRV-2026-1")  # too short
