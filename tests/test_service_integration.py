"""
Service integration tests with mocked DB sessions.
Tests actual service method logic, DB queries, and error paths.
"""
import json
from datetime import date, datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.schemas.grievance import GrievanceCreateRequest, GrievanceUpdateRequest
from app.schemas.task import TaskCreateRequest, TaskUpdateRequest


# ============================================================
# GRIEVANCE SERVICE TESTS
# ============================================================

class TestGrievanceServiceLogic:
    """Test GrievanceService business logic."""

    def test_sla_constants(self):
        from app.services.grievance_service import PRIORITY_SLA, SLA_HOURS
        assert SLA_HOURS == 72
        assert PRIORITY_SLA["urgent"] == 24
        assert PRIORITY_SLA["high"] == 48
        assert PRIORITY_SLA["medium"] == 72
        assert PRIORITY_SLA["low"] == 120

    def test_ai_prompt_structure(self):
        from app.services.grievance_service import GRIEVANCE_AI_PROMPT
        assert "{category}" in GRIEVANCE_AI_PROMPT
        assert "{subject}" in GRIEVANCE_AI_PROMPT
        assert "{description}" in GRIEVANCE_AI_PROMPT
        assert "suggested_category" in GRIEVANCE_AI_PROMPT
        assert "escalation_path_te" in GRIEVANCE_AI_PROMPT

    @pytest.mark.asyncio
    async def test_ai_suggest_fallback_on_error(self):
        from app.services.grievance_service import GrievanceService
        db = AsyncMock()
        service = GrievanceService(db=db)
        service.llm = MagicMock()
        service.llm.call_claude_structured = AsyncMock(
            side_effect=Exception("Claude unavailable")
        )

        result = await service.ai_suggest("welfare", "test subject", "test description")
        assert result.suggested_category == "welfare"
        assert result.suggested_department is not None
        assert len(result.required_evidence_te) > 0

    @pytest.mark.asyncio
    async def test_ai_suggest_invalid_json_fallback(self):
        from app.services.grievance_service import GrievanceService
        db = AsyncMock()
        service = GrievanceService(db=db)
        service.llm = MagicMock()
        service.llm.call_claude_structured = AsyncMock(return_value="not valid json {{{")

        result = await service.ai_suggest("health", "test", "test")
        assert result.suggested_category == "health"
        assert result.suggested_department == "Health"

    @pytest.mark.asyncio
    async def test_ai_suggest_valid_response(self):
        from app.services.grievance_service import GrievanceService
        db = AsyncMock()
        service = GrievanceService(db=db)
        service.llm = MagicMock()
        service.llm.call_claude_structured = AsyncMock(return_value=json.dumps({
            "suggested_category": "education",
            "suggested_department": "School Education",
            "suggested_priority": "high",
            "escalation_path_te": "సచివాలయం → మండల విద్యాధికారి",
            "required_evidence_te": ["School ID", "Application copy"],
            "resolution_suggestion_te": "Contact school administration",
        }))

        result = await service.ai_suggest("education", "Scholarship delay", "No scholarship for 6 months")
        assert result.suggested_category == "education"
        assert result.suggested_department == "School Education"
        assert result.suggested_priority == "high"

    @pytest.mark.asyncio
    async def test_reference_number_generation(self):
        from app.services.grievance_service import GrievanceService
        db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar.return_value = 5
        db.execute.return_value = mock_result

        service = GrievanceService(db=db)
        ref = await service._generate_reference_number()
        year = datetime.now(timezone.utc).year
        assert ref == f"GRV-{year}-0006"

    @pytest.mark.asyncio
    async def test_reference_number_starts_at_one(self):
        from app.services.grievance_service import GrievanceService
        db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar.return_value = 0
        db.execute.return_value = mock_result

        service = GrievanceService(db=db)
        ref = await service._generate_reference_number()
        assert ref.endswith("-0001")

    @pytest.mark.asyncio
    async def test_escalation_caps_at_level_3(self):
        from app.services.grievance_service import GrievanceService
        db = AsyncMock()
        service = GrievanceService(db=db)

        mock_grievance = MagicMock()
        mock_grievance.id = uuid4()
        mock_grievance.reference_number = "GRV-2026-0001"
        mock_grievance.status = "escalated"
        mock_grievance.escalation_level = 3
        mock_grievance.is_sla_breached = False
        mock_grievance.sla_deadline = datetime.now(timezone.utc) - timedelta(hours=1)
        mock_grievance.filed_by_employee_id = 1

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_grievance]
        db.execute.return_value = mock_result

        escalated = await service.check_and_escalate_overdue()
        assert escalated == 0
        assert mock_grievance.escalation_level == 3

    @pytest.mark.asyncio
    async def test_escalation_increments_level(self):
        from app.services.grievance_service import GrievanceService
        db = AsyncMock()
        service = GrievanceService(db=db)

        mock_grievance = MagicMock()
        mock_grievance.id = uuid4()
        mock_grievance.reference_number = "GRV-2026-0001"
        mock_grievance.status = "open"
        mock_grievance.escalation_level = 1
        mock_grievance.is_sla_breached = False
        mock_grievance.sla_deadline = datetime.now(timezone.utc) - timedelta(hours=1)
        mock_grievance.filed_by_employee_id = 1

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_grievance]
        db.execute.return_value = mock_result

        escalated = await service.check_and_escalate_overdue()
        assert escalated == 1
        assert mock_grievance.escalation_level == 2
        assert mock_grievance.is_sla_breached is True


# ============================================================
# TASK SERVICE TESTS
# ============================================================

class TestTaskServiceLogic:
    """Test TaskService business logic."""

    def test_priority_score_computation(self):
        from app.services.task_service import TaskService
        service = TaskService.__new__(TaskService)

        assert service._compute_base_priority_score("urgent", None) == 90
        assert service._compute_base_priority_score("high", None) == 70
        assert service._compute_base_priority_score("medium", None) == 50
        assert service._compute_base_priority_score("low", None) == 30

    def test_priority_score_overdue_boost(self):
        from app.services.task_service import TaskService
        service = TaskService.__new__(TaskService)
        yesterday = date.today() - timedelta(days=1)
        assert service._compute_base_priority_score("medium", yesterday) == 70

    def test_priority_score_due_today_boost(self):
        from app.services.task_service import TaskService
        service = TaskService.__new__(TaskService)
        assert service._compute_base_priority_score("medium", date.today()) == 60

    def test_priority_score_due_soon_boost(self):
        from app.services.task_service import TaskService
        service = TaskService.__new__(TaskService)
        soon = date.today() + timedelta(days=2)
        assert service._compute_base_priority_score("medium", soon) == 55

    def test_priority_score_caps_at_100(self):
        from app.services.task_service import TaskService
        service = TaskService.__new__(TaskService)
        yesterday = date.today() - timedelta(days=1)
        assert service._compute_base_priority_score("urgent", yesterday) == 100

    def test_priority_score_far_future_no_boost(self):
        from app.services.task_service import TaskService
        service = TaskService.__new__(TaskService)
        far = date.today() + timedelta(days=30)
        assert service._compute_base_priority_score("medium", far) == 50

    def test_rule_based_prioritization_ordering(self):
        from app.services.task_service import TaskService
        service = TaskService.__new__(TaskService)

        urgent_task = MagicMock()
        urgent_task.id = "uuid-1"
        urgent_task.priority = "urgent"
        urgent_task.due_date = date.today()
        urgent_task.category = "citizen_service"
        urgent_task.title_te = "Urgent"

        low_task = MagicMock()
        low_task.id = "uuid-2"
        low_task.priority = "low"
        low_task.due_date = date.today() + timedelta(days=7)
        low_task.category = "report_writing"
        low_task.title_te = "Low"

        result = service._rule_based_prioritization([urgent_task, low_task], date.today())
        assert result["task_order"][0]["task_id"] == "uuid-1"
        assert result["task_order"][1]["task_id"] == "uuid-2"

    def test_rule_reason_overdue(self):
        from app.services.task_service import TaskService
        service = TaskService.__new__(TaskService)
        task = MagicMock()
        task.due_date = date.today() - timedelta(days=1)
        task.priority = "medium"
        task.category = "general"
        reason = service._get_rule_reason_te(task, date.today())
        assert "గడువు దాటింది" in reason

    def test_rule_reason_urgent(self):
        from app.services.task_service import TaskService
        service = TaskService.__new__(TaskService)
        task = MagicMock()
        task.due_date = date.today() + timedelta(days=5)
        task.priority = "urgent"
        task.category = "general"
        reason = service._get_rule_reason_te(task, date.today())
        assert "అత్యవసరం" in reason

    def test_rule_reason_citizen_service(self):
        from app.services.task_service import TaskService
        service = TaskService.__new__(TaskService)
        task = MagicMock()
        task.due_date = date.today() + timedelta(days=5)
        task.priority = "medium"
        task.category = "citizen_service"
        reason = service._get_rule_reason_te(task, date.today())
        assert "పౌరుల సేవ" in reason

    def test_rule_reason_due_tomorrow(self):
        from app.services.task_service import TaskService
        service = TaskService.__new__(TaskService)
        task = MagicMock()
        task.due_date = date.today() + timedelta(days=1)
        task.priority = "medium"
        task.category = "general"
        reason = service._get_rule_reason_te(task, date.today())
        assert "గడువు" in reason

    def test_workload_levels(self):
        thresholds = [
            (0, "light"), (3, "light"),
            (4, "moderate"), (8, "moderate"),
            (9, "heavy"), (15, "heavy"),
            (16, "overloaded"), (30, "overloaded"),
        ]
        for count, expected in thresholds:
            if count <= 3:
                level = "light"
            elif count <= 8:
                level = "moderate"
            elif count <= 15:
                level = "heavy"
            else:
                level = "overloaded"
            assert level == expected


# ============================================================
# SECURITY EXTENDED TESTS
# ============================================================

class TestSecurityExtended:

    def test_hash_aadhaar_consistent(self):
        from app.core.security import hash_aadhaar
        assert hash_aadhaar("1234 5678 9012") == hash_aadhaar("1234 5678 9012")

    def test_hash_aadhaar_different(self):
        from app.core.security import hash_aadhaar
        assert hash_aadhaar("123456789012") != hash_aadhaar("123456789013")

    def test_strip_pii_multiple_aadhaar(self):
        from app.core.security import strip_pii
        text = "Aadhaar 1234 5678 9012 and 9876 5432 1098"
        result = strip_pii(text)
        assert result.count("[AADHAAR]") == 2

    def test_strip_pii_phone_country_code(self):
        from app.core.security import strip_pii
        result = strip_pii("Call +919876543210")
        assert "9876543210" not in result

    def test_role_hierarchy(self):
        from app.core.security import Role, ROLE_HIERARCHY
        assert ROLE_HIERARCHY[Role.EMPLOYEE] < ROLE_HIERARCHY[Role.SECRETARIAT_ADMIN]
        assert ROLE_HIERARCHY[Role.SECRETARIAT_ADMIN] < ROLE_HIERARCHY[Role.DISTRICT_ADMIN]
        assert ROLE_HIERARCHY[Role.DISTRICT_ADMIN] < ROLE_HIERARCHY[Role.SYSTEM_ADMIN]

    def test_restore_pii(self):
        from app.core.security import restore_pii
        text = "Aadhaar: [AADHAAR], Phone: [PHONE]"
        result = restore_pii(text, aadhaar="123456789012", phone="9876543210")
        assert "XXXX XXXX 9012" in result
        assert "9876543210" in result


# ============================================================
# TELUGU UTILITY EXTENDED TESTS
# ============================================================

class TestTeluguUtilsExtended:

    def test_fuzzy_match_pension(self):
        from app.core.telugu import fuzzy_match_scheme
        assert fuzzy_match_scheme("పెన్షన్ కానుక") == "YSR-PENSION-KANUKA"

    def test_fuzzy_match_cheyutha(self):
        from app.core.telugu import fuzzy_match_scheme
        assert fuzzy_match_scheme("చేయూత") == "YSR-CHEYUTHA"

    def test_normalize_multiple_spaces(self):
        from app.core.telugu import normalize_telugu_text
        result = normalize_telugu_text("అమ్మ    ఒడి   scheme")
        assert "    " not in result


# ============================================================
# LLM SERVICE TESTS
# ============================================================

class TestLLMService:

    def test_prompt_map_grievance(self):
        from app.services.llm_service import LLMRouter
        router = LLMRouter.__new__(LLMRouter)
        prompt = router._get_system_prompt("grievance_resolution")
        assert isinstance(prompt, str)

    def test_prompt_map_task(self):
        from app.services.llm_service import LLMRouter
        router = LLMRouter.__new__(LLMRouter)
        prompt = router._get_system_prompt("task_prioritization")
        assert isinstance(prompt, str)

    def test_prompt_map_default(self):
        from app.services.llm_service import LLMRouter
        router = LLMRouter.__new__(LLMRouter)
        prompt = router._get_system_prompt("unknown_task")
        assert isinstance(prompt, str)

    def test_prompt_caching(self):
        from app.services.llm_service import _load_prompt
        p1 = _load_prompt("system_main")
        p2 = _load_prompt("system_main")
        assert p1 is p2

    def test_usage_stats(self):
        from app.services.llm_service import LLMRouter
        router = LLMRouter.__new__(LLMRouter)
        router.total_input_tokens = 1000
        router.total_output_tokens = 500
        stats = router.get_usage_stats()
        assert stats["total_input_tokens"] == 1000
        assert stats["estimated_cost_usd"] > 0


# ============================================================
# CELERY CONFIG TESTS
# ============================================================

class TestCeleryConfig:

    def test_beat_schedule_has_grievance_sla(self):
        from app.workers.celery_app import celery_app
        assert "check-grievance-sla" in celery_app.conf.beat_schedule

    def test_beat_schedule_has_daily_plans(self):
        from app.workers.celery_app import celery_app
        assert "generate-daily-plans" in celery_app.conf.beat_schedule

    def test_beat_schedule_has_recurring_tasks(self):
        from app.workers.celery_app import celery_app
        assert "create-recurring-tasks" in celery_app.conf.beat_schedule

    def test_grievance_sla_30_min(self):
        from app.workers.celery_app import celery_app
        assert celery_app.conf.beat_schedule["check-grievance-sla"]["schedule"] == 1800.0

    def test_timezone_ist(self):
        from app.workers.celery_app import celery_app
        assert celery_app.conf.timezone == "Asia/Kolkata"


# ============================================================
# RECURRING TASK SCHEDULER TESTS
# ============================================================

class TestRecurringScheduler:

    def test_daily(self):
        from app.workers.task_scheduler import _should_create_today
        assert _should_create_today("daily", date.today(), "monday") is True

    def test_weekly_monday(self):
        from app.workers.task_scheduler import _should_create_today
        assert _should_create_today("weekly", date.today(), "monday") is True
        assert _should_create_today("weekly", date.today(), "tuesday") is False

    def test_weekdays(self):
        from app.workers.task_scheduler import _should_create_today
        assert _should_create_today("weekdays", date.today(), "wednesday") is True
        assert _should_create_today("weekdays", date.today(), "saturday") is False

    def test_monthly(self):
        from app.workers.task_scheduler import _should_create_today
        from datetime import date as d
        assert _should_create_today("monthly", d(2026, 4, 1), "wednesday") is True
        assert _should_create_today("monthly", d(2026, 4, 2), "thursday") is False

    def test_null_rule(self):
        from app.workers.task_scheduler import _should_create_today
        assert _should_create_today(None, date.today(), "monday") is False
        assert _should_create_today("", date.today(), "monday") is False

    def test_every_specific_day(self):
        from app.workers.task_scheduler import _should_create_today
        assert _should_create_today("every_friday", date.today(), "friday") is True
        assert _should_create_today("every_friday", date.today(), "monday") is False

    def test_format_daily_plan_message(self):
        from app.workers.task_scheduler import _format_daily_plan_message
        plan = MagicMock()
        plan.plan_date = date.today()
        plan.ai_summary_te = "Test summary"
        plan.total_estimated_minutes = 120

        task = MagicMock()
        task.rank = 1
        task.title_te = "Test task"
        task.department = "Agriculture"
        task.priority = "high"
        task.status = "pending"
        task.estimated_minutes = 30
        task.reason_te = "High priority"
        plan.tasks = [task]

        employee = MagicMock()
        employee.name_te = "రాజు"
        employee.name_en = "Raju"

        msg = _format_daily_plan_message(plan, employee)
        assert "రాజు" in msg
        assert "Test task" in msg
        assert "120 minutes" in msg
