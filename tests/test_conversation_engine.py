"""Tests for the Conversation Engine — the brain of the copilot."""
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestIntentClassification:
    """Test intent detection from Telugu and English text."""

    def _get_engine(self):
        from app.services.conversation_engine import ConversationEngine
        engine = ConversationEngine.__new__(ConversationEngine)
        return engine

    # -- Scheme queries --

    def test_telugu_scheme_query(self):
        engine = self._get_engine()
        assert engine._classify_intent("అమ్మ ఒడి అర్హత ఏమిటి?") == "scheme_query"

    def test_english_scheme_query(self):
        engine = self._get_engine()
        assert engine._classify_intent("What is Amma Vodi eligibility?") == "scheme_query"

    def test_scheme_amount_query(self):
        engine = self._get_engine()
        assert engine._classify_intent("రైతు భరోసా ఎంత వస్తుంది?") == "scheme_query"

    def test_scheme_documents_query(self):
        engine = self._get_engine()
        assert engine._classify_intent("pension documents ఏమి కావాలి?") == "scheme_query"

    def test_scheme_name_only(self):
        engine = self._get_engine()
        # Just a scheme name should match via fuzzy_match_scheme fallback
        result = engine._classify_intent("aarogyasri")
        assert result == "scheme_query"

    # -- Form help --

    def test_telugu_form_request(self):
        engine = self._get_engine()
        assert engine._classify_intent("ఫారం నింపాలి") == "form_help"

    def test_english_form_request(self):
        engine = self._get_engine()
        assert engine._classify_intent("fill application form") == "form_help"

    # -- Status check --

    def test_status_check(self):
        engine = self._get_engine()
        assert engine._classify_intent("status check pending") == "status_check"
        assert engine._classify_intent("దరఖాస్తు స్థితి") == "status_check"

    # -- Greetings --

    def test_greetings(self):
        engine = self._get_engine()
        assert engine._classify_intent("నమస్కారం") == "greeting"
        assert engine._classify_intent("hello") == "greeting"
        assert engine._classify_intent("hi") == "greeting"

    # -- Help --

    def test_help_request(self):
        engine = self._get_engine()
        assert engine._classify_intent("help") == "help"
        assert engine._classify_intent("ఏం చేయగలవు") == "help"

    # -- Thanks --

    def test_thanks(self):
        engine = self._get_engine()
        assert engine._classify_intent("ధన్యవాదాలు") == "thanks"
        assert engine._classify_intent("thanks") == "thanks"

    # -- Unclear --

    def test_unclear_intent(self):
        engine = self._get_engine()
        assert engine._classify_intent("xyz random gibberish") == "unclear"


class TestMultiTurnContext:
    """Test conversation context and follow-up handling."""

    def _get_engine(self):
        from app.services.conversation_engine import ConversationEngine
        engine = ConversationEngine.__new__(ConversationEngine)
        return engine

    def test_affirmative_followup_to_scheme(self):
        engine = self._get_engine()
        context = {"last_intent": "scheme_query", "history": [], "schemes_discussed": ["YSR-AMMA-VODI"]}
        result = engine._reclassify_with_context("అవును", context)
        assert result == "scheme_query"

    def test_yes_followup(self):
        engine = self._get_engine()
        context = {"last_intent": "form_help", "history": [], "schemes_discussed": []}
        result = engine._reclassify_with_context("yes", context)
        assert result == "form_help"

    def test_no_cancel(self):
        engine = self._get_engine()
        context = {"last_intent": "form_help", "history": [], "schemes_discussed": []}
        result = engine._reclassify_with_context("వద్దు", context)
        assert result == "no_cancel"

    def test_number_followup_for_status(self):
        engine = self._get_engine()
        context = {"last_intent": "status_check", "history": [], "schemes_discussed": []}
        result = engine._reclassify_with_context("12345678", context)
        assert result == "status_check"

    def test_continue_scheme_discussion(self):
        engine = self._get_engine()
        context = {"last_intent": "scheme_query", "history": [], "schemes_discussed": ["YSR-AMMA-VODI"]}
        result = engine._reclassify_with_context("some unclear text", context)
        assert result == "scheme_query"


class TestGreetingResponse:
    """Test greeting response generation."""

    def _get_engine(self):
        from app.services.conversation_engine import ConversationEngine
        engine = ConversationEngine.__new__(ConversationEngine)
        return engine

    def test_telugu_greeting_has_buttons(self):
        engine = self._get_engine()
        employee = MagicMock()
        employee.name_te = "రాజు"
        employee.name_en = "Raju"

        result = engine._build_greeting(employee, "te")

        assert isinstance(result, dict)
        assert result["type"] == "list"
        assert "రాజు" in result["text"]
        assert len(result["sections"][0]["rows"]) == 5

    def test_english_greeting(self):
        engine = self._get_engine()
        employee = MagicMock()
        employee.name_te = "Unknown"
        employee.name_en = "Raju"

        result = engine._build_greeting(employee, "en")

        assert isinstance(result, dict)
        assert "Raju" in result["text"]

    def test_help_menu_telugu(self):
        engine = self._get_engine()
        employee = MagicMock()

        result = engine._build_help_menu(employee, "te")

        assert "పథకాల సమాచారం" in result
        assert "ఫారం" in result
        assert "Voice" in result

    def test_thanks_response(self):
        engine = self._get_engine()
        employee = MagicMock()
        employee.name_te = "రాజు"

        result = engine._build_thanks(employee, "te")
        assert "ధన్యవాదాలు" in result


class TestSchemeListMessage:
    """Test interactive scheme list building."""

    @pytest.mark.asyncio
    async def test_scheme_list_structure(self):
        from app.services.conversation_engine import ConversationEngine
        engine = ConversationEngine.__new__(ConversationEngine)

        employee = MagicMock()
        result = await engine._build_scheme_list_message(employee, "te")

        assert result["type"] == "list"
        assert "sections" in result
        assert len(result["sections"]) >= 3  # Agriculture, Education, Health

        # Check each section has rows
        for section in result["sections"]:
            assert "title" in section
            assert "rows" in section
            for row in section["rows"]:
                assert row["id"].startswith("scheme_")
                assert "title" in row


class TestInteractiveRouting:
    """Test interactive button/list reply handling."""

    def _get_engine(self):
        from app.services.conversation_engine import ConversationEngine
        engine = ConversationEngine.__new__(ConversationEngine)
        engine.db = AsyncMock()
        engine.scheme_advisor = MagicMock()
        engine.wa = MagicMock()
        engine.llm = MagicMock()
        return engine

    @pytest.mark.asyncio
    async def test_scheme_selection_routes_to_advisor(self):
        engine = self._get_engine()
        employee = MagicMock()
        session = MagicMock()

        # Mock scheme advisor
        from app.schemas.scheme import SchemeSearchResponse
        engine.scheme_advisor.search = AsyncMock(return_value=SchemeSearchResponse(
            answer="Test answer about Amma Vodi",
            confidence=0.9,
        ))

        result = await engine._handle_interactive(
            "scheme_YSR-AMMA-VODI", "అమ్మ ఒడి", employee, session
        )
        assert "Test answer about Amma Vodi" in result

    @pytest.mark.asyncio
    async def test_no_cancel(self):
        engine = self._get_engine()
        employee = MagicMock()
        session = MagicMock()

        result = await engine._handle_interactive("no", "", employee, session)
        assert "cancel" in result.lower() or "Cancel" in result


class TestLLMPromptLoading:
    """Test that prompt templates load correctly."""

    def test_system_main_prompt_exists(self):
        from app.services.llm_service import _load_prompt
        prompt = _load_prompt("system_main")
        assert "AP Sachivalayam" in prompt
        assert "Telugu" in prompt or "తెలుగు" in prompt

    def test_eligibility_prompt_exists(self):
        from app.services.llm_service import _load_prompt
        prompt = _load_prompt("eligibility_checker")
        assert "eligible" in prompt.lower() or "ELIGIBLE" in prompt

    def test_form_extractor_prompt_exists(self):
        from app.services.llm_service import _load_prompt
        prompt = _load_prompt("form_extractor")
        assert "citizen_name" in prompt

    def test_nonexistent_prompt_returns_empty(self):
        from app.services.llm_service import _load_prompt, _prompt_cache
        _prompt_cache.pop("nonexistent_xyz", None)
        prompt = _load_prompt("nonexistent_xyz")
        assert prompt == ""
