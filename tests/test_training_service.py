"""Tests for the Training Mode feature."""
import json
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.training import TrainingSession
from app.services.training_service import SCENARIOS_FILE, TrainingService, _load_scenarios


# ---------------------------------------------------------------------------
# TestTrainingScenarios — validate the scenarios.json data file
# ---------------------------------------------------------------------------
class TestTrainingScenarios:
    """Validate the scenarios.json data file."""

    def test_scenarios_file_exists(self):
        assert SCENARIOS_FILE.exists(), f"Scenarios file not found at {SCENARIOS_FILE}"

    def test_scenarios_count_at_least_30(self):
        with open(SCENARIOS_FILE, encoding="utf-8") as f:
            scenarios = json.load(f)
        assert len(scenarios) >= 30, f"Expected at least 30 scenarios, found {len(scenarios)}"

    def test_scenario_has_required_fields(self):
        with open(SCENARIOS_FILE, encoding="utf-8") as f:
            scenarios = json.load(f)
        required_fields = {"id", "difficulty", "category", "scenario_te", "scenario_en", "key_points", "model_answer_te"}
        for scenario in scenarios:
            missing = required_fields - set(scenario.keys())
            assert not missing, f"Scenario {scenario.get('id', '?')} missing fields: {missing}"

    def test_scenario_difficulties_valid(self):
        with open(SCENARIOS_FILE, encoding="utf-8") as f:
            scenarios = json.load(f)
        valid_difficulties = {"easy", "medium", "hard"}
        for scenario in scenarios:
            assert scenario["difficulty"] in valid_difficulties, (
                f"Scenario {scenario['id']} has invalid difficulty: {scenario['difficulty']}"
            )


# ---------------------------------------------------------------------------
# TestTrainingModel — validate the SQLAlchemy model
# ---------------------------------------------------------------------------
class TestTrainingModel:
    """Test TrainingSession SQLAlchemy model structure."""

    def test_training_session_tablename(self):
        assert TrainingSession.__tablename__ == "training_sessions"

    def test_training_session_defaults(self):
        cols = TrainingSession.__table__.columns
        assert cols["difficulty"].default.arg == "easy"
        assert cols["category"].default.arg == "scheme_query"

    def test_training_score_range(self):
        """SmallInteger column exists for ai_score (0-100 enforced at app level)."""
        cols = TrainingSession.__table__.columns
        assert "ai_score" in cols
        # SmallInteger type check
        from sqlalchemy import SmallInteger
        assert isinstance(cols["ai_score"].type, SmallInteger)


# ---------------------------------------------------------------------------
# TestScenarioSelection — test get_next_scenario logic
# ---------------------------------------------------------------------------
class TestScenarioSelection:
    """Test scenario selection logic."""

    @pytest.fixture
    def mock_db(self):
        db = AsyncMock()
        return db

    @pytest.fixture
    def service(self, mock_db):
        return TrainingService(mock_db)

    @pytest.mark.asyncio
    async def test_get_next_unattempted_first(self, service, mock_db):
        """When employee has no completed scenarios, return first scenario."""
        # Mock empty completed list
        mock_result = MagicMock()
        mock_result.all.return_value = []
        mock_db.execute.return_value = mock_result

        scenario = await service.get_next_scenario(employee_id=1)
        assert scenario is not None
        assert scenario["id"] == "TR001"

    @pytest.mark.asyncio
    async def test_get_next_low_score_prioritized(self, service, mock_db):
        """When all attempted but some have low scores, return lowest scored."""
        scenarios = _load_scenarios()
        # Mock: all scenarios completed, TR003 has lowest score
        rows = []
        for s in scenarios:
            row = MagicMock()
            row.scenario_id = s["id"]
            row.best_score = 90 if s["id"] != "TR003" else 30
            rows.append(row)

        mock_result = MagicMock()
        mock_result.all.return_value = rows
        mock_db.execute.return_value = mock_result

        scenario = await service.get_next_scenario(employee_id=1)
        assert scenario is not None
        assert scenario["id"] == "TR003"

    @pytest.mark.asyncio
    async def test_filter_by_difficulty(self, service, mock_db):
        """Filter scenarios by difficulty level."""
        mock_result = MagicMock()
        mock_result.all.return_value = []
        mock_db.execute.return_value = mock_result

        scenario = await service.get_next_scenario(employee_id=1, difficulty="hard")
        assert scenario is not None
        assert scenario["difficulty"] == "hard"

    @pytest.mark.asyncio
    async def test_filter_by_category(self, service, mock_db):
        """Filter scenarios by category."""
        mock_result = MagicMock()
        mock_result.all.return_value = []
        mock_db.execute.return_value = mock_result

        scenario = await service.get_next_scenario(employee_id=1, category="grievance_handling")
        assert scenario is not None
        assert scenario["category"] == "grievance_handling"


# ---------------------------------------------------------------------------
# TestEvaluation — test evaluate_response logic
# ---------------------------------------------------------------------------
class TestEvaluation:
    """Test evaluation logic."""

    @pytest.fixture
    def mock_db(self):
        return AsyncMock()

    @pytest.fixture
    def service(self, mock_db):
        return TrainingService(mock_db)

    @pytest.mark.asyncio
    async def test_evaluate_updates_session(self, service, mock_db):
        """Verify session is updated with score and feedback after evaluation."""
        session_id = uuid.uuid4()
        mock_session = MagicMock(spec=TrainingSession)
        mock_session.id = session_id
        mock_session.scenario_id = "TR001"
        mock_session.started_at = datetime.now(timezone.utc) - timedelta(minutes=2)
        mock_session.employee_response = None
        mock_session.ai_score = None

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_session
        mock_db.execute.return_value = mock_result

        claude_response = json.dumps({
            "score": 85,
            "key_points_covered": [True, True, True, True, False, False],
            "feedback_te": "బాగా చెప్పారు!",
            "feedback_en": "Good response!",
        })

        with patch.object(service.llm, "call_claude_structured", return_value=claude_response):
            result = await service.evaluate_response(str(session_id), "Test response")

        assert result["score"] == 85
        assert result["feedback_en"] == "Good response!"
        assert mock_session.ai_score == 85
        assert mock_session.completed_at is not None

    @pytest.mark.asyncio
    async def test_evaluate_handles_json_error(self, service, mock_db):
        """Verify fallback when Claude returns invalid JSON."""
        session_id = uuid.uuid4()
        mock_session = MagicMock(spec=TrainingSession)
        mock_session.id = session_id
        mock_session.scenario_id = "TR001"
        mock_session.started_at = datetime.now(timezone.utc) - timedelta(minutes=1)

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_session
        mock_db.execute.return_value = mock_result

        with patch.object(service.llm, "call_claude_structured", return_value="not valid json"):
            result = await service.evaluate_response(str(session_id), "Test response")

        # Should get fallback score of 50
        assert result["score"] == 50
        assert "Evaluation error" in result["feedback_en"]

    @pytest.mark.asyncio
    async def test_evaluate_calculates_time_taken(self, service, mock_db):
        """Verify time_taken_seconds is calculated from started_at."""
        session_id = uuid.uuid4()
        started = datetime.now(timezone.utc) - timedelta(seconds=120)
        mock_session = MagicMock(spec=TrainingSession)
        mock_session.id = session_id
        mock_session.scenario_id = "TR001"
        mock_session.started_at = started

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_session
        mock_db.execute.return_value = mock_result

        claude_response = json.dumps({
            "score": 70,
            "key_points_covered": [True, True, False, False, False, False],
            "feedback_te": "OK",
            "feedback_en": "OK",
        })

        with patch.object(service.llm, "call_claude_structured", return_value=claude_response):
            await service.evaluate_response(str(session_id), "Test response")

        # time_taken should be approximately 120 seconds (allow some tolerance)
        assert mock_session.time_taken_seconds >= 119

    @pytest.mark.asyncio
    async def test_evaluate_session_not_found(self, service, mock_db):
        """Verify error returned for non-existent session."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        result = await service.evaluate_response(str(uuid.uuid4()), "Test response")
        assert "error" in result
        assert result["error"] == "Training session not found"


# ---------------------------------------------------------------------------
# TestProgress — test progress aggregation
# ---------------------------------------------------------------------------
class TestProgress:
    """Test progress aggregation."""

    @pytest.fixture
    def mock_db(self):
        return AsyncMock()

    @pytest.fixture
    def service(self, mock_db):
        return TrainingService(mock_db)

    @pytest.mark.asyncio
    async def test_progress_aggregation(self, service, mock_db):
        """Verify progress stats are correctly calculated."""
        # Mock stats result
        stats_row = MagicMock()
        stats_row.total_sessions = 15
        stats_row.avg_score = 72.5
        stats_row.best_score = 95
        stats_row.passed = 10

        stats_result = MagicMock()
        stats_result.one.return_value = stats_row

        # Mock unique count result
        unique_result = MagicMock()
        unique_result.scalar.return_value = 12

        mock_db.execute.side_effect = [stats_result, unique_result]

        progress = await service.get_employee_progress(employee_id=1)

        assert progress["total_sessions"] == 15
        assert progress["average_score"] == 72.5
        assert progress["best_score"] == 95
        assert progress["passed_count"] == 10
        assert progress["unique_scenarios_completed"] == 12

    @pytest.mark.asyncio
    async def test_progress_empty(self, service, mock_db):
        """Verify zero values when no sessions exist."""
        stats_row = MagicMock()
        stats_row.total_sessions = 0
        stats_row.avg_score = None
        stats_row.best_score = None
        stats_row.passed = 0

        stats_result = MagicMock()
        stats_result.one.return_value = stats_row

        unique_result = MagicMock()
        unique_result.scalar.return_value = 0

        mock_db.execute.side_effect = [stats_result, unique_result]

        progress = await service.get_employee_progress(employee_id=999)

        assert progress["total_sessions"] == 0
        assert progress["average_score"] == 0.0
        assert progress["best_score"] == 0
        assert progress["completion_percentage"] == 0.0

    @pytest.mark.asyncio
    async def test_completion_percentage(self, service, mock_db):
        """Verify completion percentage calculation."""
        total_scenarios = len(_load_scenarios())

        stats_row = MagicMock()
        stats_row.total_sessions = total_scenarios
        stats_row.avg_score = 80.0
        stats_row.best_score = 100
        stats_row.passed = total_scenarios

        stats_result = MagicMock()
        stats_result.one.return_value = stats_row

        unique_result = MagicMock()
        unique_result.scalar.return_value = total_scenarios

        mock_db.execute.side_effect = [stats_result, unique_result]

        progress = await service.get_employee_progress(employee_id=1)

        assert progress["completion_percentage"] == 100.0


# ---------------------------------------------------------------------------
# TestLeaderboard — test leaderboard logic
# ---------------------------------------------------------------------------
class TestLeaderboard:
    """Test leaderboard."""

    @pytest.fixture
    def mock_db(self):
        return AsyncMock()

    @pytest.fixture
    def service(self, mock_db):
        return TrainingService(mock_db)

    @pytest.mark.asyncio
    async def test_leaderboard_sorted_by_avg_score(self, service, mock_db):
        """Verify leaderboard entries have rank assigned correctly."""
        rows = []
        for i, (eid, score) in enumerate([(1, 95.0), (2, 85.0), (3, 75.0)]):
            row = MagicMock()
            row.employee_id = eid
            row.avg_score = score
            row.sessions = 10
            rows.append(row)

        mock_result = MagicMock()
        mock_result.all.return_value = rows
        mock_db.execute.return_value = mock_result

        leaderboard = await service.get_leaderboard(limit=10)

        assert len(leaderboard) == 3
        assert leaderboard[0]["rank"] == 1
        assert leaderboard[0]["avg_score"] == 95.0
        assert leaderboard[2]["rank"] == 3
        assert leaderboard[2]["avg_score"] == 75.0

    @pytest.mark.asyncio
    async def test_leaderboard_respects_limit(self, service, mock_db):
        """Verify limit parameter is used."""
        rows = []
        for i in range(2):
            row = MagicMock()
            row.employee_id = i + 1
            row.avg_score = 90.0 - i * 10
            row.sessions = 5
            rows.append(row)

        mock_result = MagicMock()
        mock_result.all.return_value = rows
        mock_db.execute.return_value = mock_result

        leaderboard = await service.get_leaderboard(limit=2)
        assert len(leaderboard) == 2


# ---------------------------------------------------------------------------
# TestTrainingConversationFlow — integration-level checks
# ---------------------------------------------------------------------------
class TestTrainingConversationFlow:
    """Test training integration with conversation engine."""

    def test_training_intent_keywords_exist(self):
        """Verify INTENT_KEYWORDS has training entries."""
        from app.services.conversation_engine import INTENT_KEYWORDS
        assert "training" in INTENT_KEYWORDS
        keywords = INTENT_KEYWORDS["training"]
        assert "training" in keywords
        assert "practice" in keywords
        assert "ట్రైనింగ్" in keywords

    def test_training_scenario_content_is_bilingual(self):
        """All scenarios must have both Telugu and English text."""
        with open(SCENARIOS_FILE, encoding="utf-8") as f:
            scenarios = json.load(f)
        for scenario in scenarios:
            assert scenario.get("scenario_te"), f"Scenario {scenario['id']} missing Telugu text"
            assert scenario.get("scenario_en"), f"Scenario {scenario['id']} missing English text"
            assert scenario.get("model_answer_te"), f"Scenario {scenario['id']} missing Telugu model answer"

    def test_scenarios_reference_valid_schemes(self):
        """All expected_scheme values should match known scheme codes."""
        # Gather all scheme codes from scheme JSON files
        schemes_dir = Path(__file__).parent.parent / "app" / "data" / "schemes"
        known_codes = set()
        for f in schemes_dir.glob("*.json"):
            with open(f, encoding="utf-8") as fh:
                data = json.load(fh)
                known_codes.add(data["scheme_code"])

        with open(SCENARIOS_FILE, encoding="utf-8") as f:
            scenarios = json.load(f)
        for scenario in scenarios:
            code = scenario.get("expected_scheme")
            if code:
                assert code in known_codes, (
                    f"Scenario {scenario['id']} references unknown scheme: {code}. "
                    f"Known codes: {sorted(known_codes)}"
                )
