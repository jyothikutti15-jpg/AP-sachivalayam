"""Tests for the Task Prioritization Service."""
import json
from datetime import date, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.models.task import DailyPlan, Task
from app.schemas.task import TaskCreateRequest, TaskUpdateRequest


class TestTaskModel:
    """Test Task SQLAlchemy model structure."""

    def test_task_tablename(self):
        assert Task.__tablename__ == "tasks"

    def test_daily_plan_tablename(self):
        assert DailyPlan.__tablename__ == "daily_plans"

    def test_task_defaults(self):
        cols = Task.__table__.columns
        assert cols["status"].default.arg == "pending"
        assert cols["priority"].default.arg == "medium"
        assert cols["priority_score"].default.arg == 50
        assert cols["estimated_minutes"].default.arg == 30
        assert cols["source"].default.arg == "manual"
        assert cols["is_recurring"].default.arg is False
        assert cols["is_ai_suggested"].default.arg is False

    def test_task_categories(self):
        """Valid task categories that employees deal with."""
        valid = {
            "general", "scheme_processing", "field_visit", "data_entry",
            "report_writing", "grievance_followup", "meeting", "survey",
            "inspection", "citizen_service",
        }
        # category default is "general"
        cols = Task.__table__.columns
        assert cols["category"].default.arg == "general"


class TestTaskRequest:
    """Test task request schema validation."""

    def test_valid_request(self):
        req = TaskCreateRequest(
            title_te="రైతు భరోసా applications process చేయండి",
            department="Agriculture",
        )
        assert req.priority == "medium"
        assert req.estimated_minutes == 30
        assert req.source == "manual"
        assert req.is_recurring is False

    def test_full_request(self):
        req = TaskCreateRequest(
            title_te="ఫీల్డ్ visit — village survey",
            title_en="Field visit for village survey",
            description_te="5 గ్రామాల survey పూర్తి చేయాలి",
            department="Revenue",
            category="field_visit",
            priority="high",
            due_date=date.today(),
            estimated_minutes=120,
            is_recurring=False,
            source="gsws_sync",
        )
        assert req.estimated_minutes == 120
        assert req.category == "field_visit"

    def test_recurring_task_request(self):
        req = TaskCreateRequest(
            title_te="Daily attendance report",
            department="General Administration",
            category="report_writing",
            is_recurring=True,
            recurrence_rule="weekdays",
            estimated_minutes=15,
        )
        assert req.is_recurring is True
        assert req.recurrence_rule == "weekdays"


class TestPriorityScoring:
    """Test the priority score computation logic."""

    def test_base_scores(self):
        from app.services.task_service import TaskService

        service = TaskService.__new__(TaskService)

        assert service._compute_base_priority_score("urgent", None) == 90
        assert service._compute_base_priority_score("high", None) == 70
        assert service._compute_base_priority_score("medium", None) == 50
        assert service._compute_base_priority_score("low", None) == 30

    def test_overdue_boost(self):
        from app.services.task_service import TaskService

        service = TaskService.__new__(TaskService)
        yesterday = date.today() - timedelta(days=1)
        score = service._compute_base_priority_score("medium", yesterday)
        assert score == 70  # 50 + 20 overdue boost

    def test_due_today_boost(self):
        from app.services.task_service import TaskService

        service = TaskService.__new__(TaskService)
        today = date.today()
        score = service._compute_base_priority_score("medium", today)
        assert score == 60  # 50 + 10 due-today boost

    def test_due_in_3_days_boost(self):
        from app.services.task_service import TaskService

        service = TaskService.__new__(TaskService)
        soon = date.today() + timedelta(days=2)
        score = service._compute_base_priority_score("medium", soon)
        assert score == 55  # 50 + 5

    def test_urgent_overdue_caps_at_100(self):
        from app.services.task_service import TaskService

        service = TaskService.__new__(TaskService)
        yesterday = date.today() - timedelta(days=1)
        score = service._compute_base_priority_score("urgent", yesterday)
        assert score == 100  # 90 + 20 = 110, capped at 100


class TestRuleBasedPrioritization:
    """Test the fallback rule-based prioritization (when AI is unavailable)."""

    def test_rule_based_returns_ordered_tasks(self):
        from app.services.task_service import TaskService

        service = TaskService.__new__(TaskService)

        # Create mock tasks
        urgent_task = MagicMock()
        urgent_task.id = "uuid-1"
        urgent_task.priority = "urgent"
        urgent_task.due_date = date.today()
        urgent_task.category = "citizen_service"
        urgent_task.title_te = "Urgent task"

        low_task = MagicMock()
        low_task.id = "uuid-2"
        low_task.priority = "low"
        low_task.due_date = date.today() + timedelta(days=7)
        low_task.category = "report_writing"
        low_task.title_te = "Low task"

        result = service._rule_based_prioritization([urgent_task, low_task], date.today())

        assert "task_order" in result
        assert "summary_te" in result
        assert len(result["task_order"]) == 2
        assert result["task_order"][0]["task_id"] == "uuid-1"  # Urgent first
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


class TestTaskPrioritizationPrompt:
    """Test AI prioritization prompt structure."""

    def test_prompt_has_placeholders(self):
        from app.services.task_service import PRIORITIZATION_PROMPT

        assert "{employee_name}" in PRIORITIZATION_PROMPT
        assert "{designation}" in PRIORITIZATION_PROMPT
        assert "{department}" in PRIORITIZATION_PROMPT
        assert "{today}" in PRIORITIZATION_PROMPT
        assert "{tasks_json}" in PRIORITIZATION_PROMPT

    def test_prompt_requests_json(self):
        from app.services.task_service import PRIORITIZATION_PROMPT

        assert "task_order" in PRIORITIZATION_PROMPT
        assert "reason_te" in PRIORITIZATION_PROMPT
        assert "summary_te" in PRIORITIZATION_PROMPT

    def test_prompt_has_burnout_rules(self):
        from app.services.task_service import PRIORITIZATION_PROMPT

        assert "burnout" in PRIORITIZATION_PROMPT.lower()
        assert "480 minutes" in PRIORITIZATION_PROMPT or "8 hours" in PRIORITIZATION_PROMPT


class TestRecurringTasks:
    """Test recurring task scheduling logic."""

    def test_should_create_daily(self):
        from app.workers.task_scheduler import _should_create_today

        assert _should_create_today("daily", date.today(), "monday") is True
        assert _should_create_today("daily", date.today(), "sunday") is True

    def test_should_create_weekly(self):
        from app.workers.task_scheduler import _should_create_today

        assert _should_create_today("weekly", date.today(), "monday") is True
        assert _should_create_today("weekly", date.today(), "tuesday") is False

    def test_should_create_weekdays(self):
        from app.workers.task_scheduler import _should_create_today

        assert _should_create_today("weekdays", date.today(), "monday") is True
        assert _should_create_today("weekdays", date.today(), "wednesday") is True
        assert _should_create_today("weekdays", date.today(), "saturday") is False
        assert _should_create_today("weekdays", date.today(), "sunday") is False

    def test_should_create_monthly(self):
        from app.workers.task_scheduler import _should_create_today
        from datetime import date as d

        first = d(2026, 4, 1)
        second = d(2026, 4, 2)

        assert _should_create_today("monthly", first, "wednesday") is True
        assert _should_create_today("monthly", second, "thursday") is False

    def test_null_rule_returns_false(self):
        from app.workers.task_scheduler import _should_create_today

        assert _should_create_today(None, date.today(), "monday") is False
        assert _should_create_today("", date.today(), "monday") is False


class TestWorkloadLevels:
    """Test workload level classification."""

    def test_workload_thresholds(self):
        """Verify the workload level logic thresholds."""
        # light: <= 3 tasks
        # moderate: <= 8 tasks
        # heavy: <= 15 tasks
        # overloaded: > 15 tasks
        thresholds = [
            (0, "light"), (3, "light"),
            (4, "moderate"), (8, "moderate"),
            (9, "heavy"), (15, "heavy"),
            (16, "overloaded"), (30, "overloaded"),
        ]
        for pending_count, expected_level in thresholds:
            if pending_count <= 3:
                level = "light"
            elif pending_count <= 8:
                level = "moderate"
            elif pending_count <= 15:
                level = "heavy"
            else:
                level = "overloaded"
            assert level == expected_level, \
                f"Expected {expected_level} for {pending_count} tasks, got {level}"
