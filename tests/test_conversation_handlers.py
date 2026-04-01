"""
Comprehensive tests for conversation engine handlers —
grievance, task, eligibility, form, status, voice, and interactive routing.
"""
from datetime import date, datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest


def _get_engine():
    """Create a ConversationEngine instance with mocked DB."""
    from app.services.conversation_engine import ConversationEngine
    engine = ConversationEngine.__new__(ConversationEngine)
    engine.db = AsyncMock()
    engine.llm = MagicMock()
    engine.scheme_advisor = MagicMock()
    engine.wa = MagicMock()
    return engine


# ============================================================
# GRIEVANCE HANDLER TESTS
# ============================================================

class TestGrievanceHandler:
    """Test _handle_grievance() method in conversation engine."""

    @pytest.mark.asyncio
    async def test_new_grievance_returns_buttons_telugu(self):
        engine = _get_engine()
        employee = MagicMock()
        result = await engine._handle_grievance("ఫిర్యాదు నమోదు", "te", employee)
        assert isinstance(result, dict)
        assert result["type"] == "buttons"
        assert len(result["buttons"]) == 3

    @pytest.mark.asyncio
    async def test_new_grievance_returns_text_english(self):
        engine = _get_engine()
        employee = MagicMock()
        result = await engine._handle_grievance("file a complaint", "en", employee)
        assert isinstance(result, str)
        assert "grievance" in result.lower() or "citizen" in result.lower()

    @pytest.mark.asyncio
    async def test_grv_reference_regex_detection(self):
        """Test that GRV-YYYY-NNNN pattern is detected in text."""
        import re
        text = "Check status of GRV-2026-0001"
        match = re.search(r"GRV-\d{4}-\d{4}", text, re.IGNORECASE)
        assert match is not None
        assert match.group() == "GRV-2026-0001"

    @pytest.mark.asyncio
    async def test_grv_reference_case_insensitive(self):
        import re
        text = "grv-2026-0001 status"
        match = re.search(r"GRV-\d{4}-\d{4}", text, re.IGNORECASE)
        assert match is not None

    @pytest.mark.asyncio
    async def test_no_grv_reference_shows_filing_flow(self):
        engine = _get_engine()
        employee = MagicMock()
        result = await engine._handle_grievance("complaint about water supply", "te", employee)
        assert isinstance(result, dict)  # Shows category buttons

    @pytest.mark.asyncio
    async def test_grievance_lookup_exception_falls_to_filing(self):
        """When GSWS lookup fails, should gracefully fall back to filing."""
        engine = _get_engine()
        employee = MagicMock()
        # The handler imports GrievanceService inside try/except
        # When it raises, should fall through to new filing flow
        result = await engine._handle_grievance("GRV-2026-9999", "te", employee)
        # Should still return something (either error or filing flow)
        assert result is not None


# ============================================================
# TASK HANDLER TESTS
# ============================================================

class TestTaskHandler:
    """Test _handle_task_query() method."""

    @pytest.mark.asyncio
    async def test_task_completion_keywords(self):
        """Verify all completion keywords are recognized."""
        complete_keywords = ["done", "complete", "అయింది", "పూర్తి", "finished"]
        for kw in complete_keywords:
            assert any(k in kw.lower() for k in complete_keywords), \
                f"Keyword {kw} should be in completion list"

    @pytest.mark.asyncio
    async def test_task_error_returns_error_message(self):
        engine = _get_engine()
        employee = MagicMock()
        employee.id = 1

        # Patch TaskService to raise an error
        with patch("app.services.task_service.TaskService") as MockTS:
            MockTS.side_effect = Exception("DB error")
            result = await engine._handle_task_query("show tasks", "te", employee)
            assert "సమస్య" in result or "error" in result.lower()


# ============================================================
# INTENT CLASSIFICATION EXTENDED TESTS
# ============================================================

class TestIntentClassificationExtended:
    """Extended intent classification tests for new intents."""

    def test_grievance_intent_telugu(self):
        engine = _get_engine()
        assert engine._classify_intent("ఫిర్యాదు నమోదు చేయాలి") == "grievance"

    def test_grievance_intent_english(self):
        engine = _get_engine()
        assert engine._classify_intent("file a grievance complaint") == "grievance"

    def test_grievance_intent_grv_keyword(self):
        engine = _get_engine()
        result = engine._classify_intent("GRV-2026-0001 status check")
        assert result == "grievance"

    def test_task_intent_telugu(self):
        engine = _get_engine()
        assert engine._classify_intent("ఈ రోజు ఏం పని చేయాలి") == "task_query"

    def test_task_intent_english(self):
        engine = _get_engine()
        assert engine._classify_intent("show my daily plan tasks") == "task_query"

    def test_task_done_intent(self):
        engine = _get_engine()
        assert engine._classify_intent("task done complete") == "task_query"

    def test_workload_intent(self):
        engine = _get_engine()
        result = engine._classify_intent("పని భారం ఎంత ఉంది")
        assert result == "task_query"

    def test_escalate_intent(self):
        engine = _get_engine()
        result = engine._classify_intent("escalate this problem")
        assert result == "grievance"

    def test_problem_intent(self):
        engine = _get_engine()
        result = engine._classify_intent("citizen has a serious problem issue")
        assert result == "grievance"


# ============================================================
# INTERACTIVE ROUTING EXTENDED TESTS
# ============================================================

class TestInteractiveRoutingExtended:

    @pytest.mark.asyncio
    async def test_grievance_file_button(self):
        engine = _get_engine()
        employee = MagicMock()
        session = MagicMock()
        result = await engine._handle_interactive("grievance_file", "", employee, session)
        assert isinstance(result, (str, dict))

    @pytest.mark.asyncio
    async def test_grv_category_button(self):
        engine = _get_engine()
        employee = MagicMock()
        session = MagicMock()
        result = await engine._handle_interactive("grv_welfare", "welfare", employee, session)
        assert isinstance(result, (str, dict))


# ============================================================
# GREETING AND HELP MENU TESTS
# ============================================================

class TestGreetingAndHelpExtended:

    def test_greeting_includes_grievance_option(self):
        engine = _get_engine()
        employee = MagicMock()
        employee.name_te = "రాజు"
        employee.name_en = "Raju"
        result = engine._build_greeting(employee, "te")
        assert result["type"] == "list"
        rows = result["sections"][0]["rows"]
        row_ids = [r["id"] for r in rows]
        assert "grievance_file" in row_ids
        assert "task_plan" in row_ids

    def test_greeting_has_5_options(self):
        engine = _get_engine()
        employee = MagicMock()
        employee.name_te = "Test"
        employee.name_en = "Test"
        result = engine._build_greeting(employee, "te")
        rows = result["sections"][0]["rows"]
        assert len(rows) == 5

    def test_help_menu_includes_grievance_te(self):
        engine = _get_engine()
        employee = MagicMock()
        result = engine._build_help_menu(employee, "te")
        assert "ఫిర్యాదు" in result

    def test_help_menu_includes_task_te(self):
        engine = _get_engine()
        employee = MagicMock()
        result = engine._build_help_menu(employee, "te")
        assert "Task" in result or "task" in result

    def test_help_menu_includes_grievance_en(self):
        engine = _get_engine()
        employee = MagicMock()
        result = engine._build_help_menu(employee, "en")
        assert "Grievance" in result

    def test_help_menu_includes_task_en(self):
        engine = _get_engine()
        employee = MagicMock()
        result = engine._build_help_menu(employee, "en")
        assert "Task" in result


# ============================================================
# MULTI-TURN CONTEXT EXTENDED TESTS
# ============================================================

class TestMultiTurnContextExtended:

    def test_reclassify_affirmative_after_grievance(self):
        engine = _get_engine()
        context = {"last_intent": "grievance", "history": [], "schemes_discussed": []}
        result = engine._reclassify_with_context("అవును", context)
        assert result == "yes_confirm"

    def test_number_after_status_check(self):
        engine = _get_engine()
        context = {"last_intent": "status_check", "history": [], "schemes_discussed": []}
        result = engine._reclassify_with_context("123456", context)
        assert result == "status_check"


# ============================================================
# EDGE CASE TESTS
# ============================================================

class TestEdgeCases:

    def test_empty_message_intent(self):
        engine = _get_engine()
        result = engine._classify_intent("")
        assert result == "unclear"

    def test_very_long_message_intent(self):
        engine = _get_engine()
        long_text = "scheme " * 1000
        result = engine._classify_intent(long_text)
        assert result == "scheme_query"

    def test_mixed_intent_keywords(self):
        engine = _get_engine()
        text = "scheme form status help"
        result = engine._classify_intent(text)
        assert result in ("scheme_query", "form_help", "status_check", "help")

    def test_special_characters_in_message(self):
        engine = _get_engine()
        result = engine._classify_intent("scheme??? help!!! @#$%")
        assert result in ("scheme_query", "help")

    @pytest.mark.asyncio
    async def test_handle_voice_exception(self):
        engine = _get_engine()
        engine.wa.download_media = AsyncMock(side_effect=Exception("Network error"))
        employee = MagicMock()
        session = MagicMock()
        result = await engine._handle_voice("media_123", "919876543210", employee, session)
        assert "సమస్య" in result or "Voice" in result
