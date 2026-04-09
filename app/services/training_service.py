"""Training Service — Manages practice scenarios and AI evaluation for employees."""
import json
import uuid as uuid_mod
from datetime import datetime, timezone
from pathlib import Path

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.training import TrainingSession
from app.services.llm_service import LLMRouter

logger = structlog.get_logger()

SCENARIOS_FILE = Path(__file__).parent.parent / "data" / "training" / "scenarios.json"
_scenarios_cache: list[dict] | None = None

EVALUATION_PROMPT = """You are an AI training evaluator for AP Sachivalayam employees.

Score the employee's response to a citizen query. The employee is practicing how to answer scheme-related questions.

SCENARIO: {scenario}
EXPECTED KEY POINTS: {key_points}
MODEL ANSWER: {model_answer}
EMPLOYEE'S RESPONSE: {employee_response}

Evaluate and respond in JSON:
{{
    "score": 0-100,
    "key_points_covered": [true/false for each expected key point],
    "feedback_te": "Telugu coaching feedback (what they got right, what to improve, tips)",
    "feedback_en": "English coaching feedback"
}}

SCORING RULES:
- 90-100: All key points covered accurately
- 70-89: Most key points covered, minor gaps
- 50-69: Some key points covered, significant gaps
- 30-49: Few key points, needs improvement
- 0-29: Incorrect or irrelevant response"""


def _load_scenarios() -> list[dict]:
    global _scenarios_cache
    if _scenarios_cache is None:
        with open(SCENARIOS_FILE, encoding="utf-8") as f:
            _scenarios_cache = json.load(f)
    return _scenarios_cache


class TrainingService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.llm = LLMRouter()

    async def get_next_scenario(
        self, employee_id: int, difficulty: str | None = None, category: str | None = None
    ) -> dict | None:
        """Pick a scenario the employee hasn't done or scored poorly on."""
        scenarios = _load_scenarios()

        # Get completed scenarios
        result = await self.db.execute(
            select(TrainingSession.scenario_id, func.max(TrainingSession.ai_score).label("best_score"))
            .where(TrainingSession.employee_id == employee_id)
            .group_by(TrainingSession.scenario_id)
        )
        completed = {row.scenario_id: row.best_score for row in result.all()}

        # Filter by difficulty/category
        candidates = scenarios
        if difficulty:
            candidates = [s for s in candidates if s["difficulty"] == difficulty]
        if category:
            candidates = [s for s in candidates if s["category"] == category]

        # Prioritize: not attempted > low score > high score
        not_attempted = [s for s in candidates if s["id"] not in completed]
        if not_attempted:
            return not_attempted[0]

        low_score = [s for s in candidates if completed.get(s["id"], 0) < 70]
        if low_score:
            low_score.sort(key=lambda s: completed.get(s["id"], 0))
            return low_score[0]

        # All done well — return first for re-practice
        return candidates[0] if candidates else None

    async def start_session(self, employee_id: int, scenario_id: str) -> TrainingSession:
        """Create a training session when employee starts a scenario."""
        scenario = self._get_scenario_by_id(scenario_id)
        session = TrainingSession(
            employee_id=employee_id,
            scenario_id=scenario_id,
            difficulty=scenario.get("difficulty", "easy") if scenario else "easy",
            category=scenario.get("category", "scheme_query") if scenario else "scheme_query",
        )
        self.db.add(session)
        await self.db.flush()
        return session

    async def evaluate_response(
        self, session_id, employee_response: str
    ) -> dict:
        """Evaluate the employee's response using Claude."""
        if isinstance(session_id, str):
            session_id = uuid_mod.UUID(session_id)

        result = await self.db.execute(
            select(TrainingSession).where(TrainingSession.id == session_id)
        )
        session = result.scalar_one_or_none()
        if not session:
            return {"error": "Training session not found"}

        scenario = self._get_scenario_by_id(session.scenario_id)
        if not scenario:
            return {"error": "Scenario not found"}

        # Call Claude for evaluation
        prompt = EVALUATION_PROMPT.format(
            scenario=scenario.get("scenario_en", scenario.get("scenario_te", "")),
            key_points=json.dumps(scenario["key_points"]),
            model_answer=scenario.get("model_answer_te", ""),
            employee_response=employee_response,
        )

        try:
            response = await self.llm.call_claude_structured(
                prompt="Evaluate this training response.",
                system_prompt=prompt,
                max_tokens=1000,
            )
            evaluation = json.loads(response)
        except (json.JSONDecodeError, Exception) as e:
            logger.error("Training evaluation failed", error=str(e))
            evaluation = {
                "score": 50,
                "key_points_covered": [False] * len(scenario.get("key_points", [])),
                "feedback_te": "మూల్యాంకనంలో లోపం. దయచేసి మళ్ళీ ప్రయత్నించండి.",
                "feedback_en": "Evaluation error. Please try again.",
            }

        # Update session
        now = datetime.now(timezone.utc)
        session.employee_response = employee_response
        session.ai_score = evaluation.get("score", 0)
        session.ai_feedback_te = evaluation.get("feedback_te", "")
        session.ai_feedback_en = evaluation.get("feedback_en", "")
        session.key_points_covered = {"covered": evaluation.get("key_points_covered", [])}
        session.completed_at = now
        if session.started_at:
            session.time_taken_seconds = int((now - session.started_at).total_seconds())
        await self.db.flush()

        return {
            "session_id": str(session.id),
            "score": evaluation.get("score", 0),
            "feedback_te": evaluation.get("feedback_te", ""),
            "feedback_en": evaluation.get("feedback_en", ""),
            "key_points_covered": evaluation.get("key_points_covered", []),
            "key_points_expected": scenario.get("key_points", []),
        }

    async def get_employee_progress(self, employee_id: int) -> dict:
        """Aggregate training progress for an employee."""
        result = await self.db.execute(
            select(
                func.count(TrainingSession.id).label("total_sessions"),
                func.avg(TrainingSession.ai_score).label("avg_score"),
                func.max(TrainingSession.ai_score).label("best_score"),
                func.count().filter(TrainingSession.ai_score >= 70).label("passed"),
            ).where(
                TrainingSession.employee_id == employee_id,
                TrainingSession.ai_score.isnot(None),
            )
        )
        stats = result.one()

        total_scenarios = len(_load_scenarios())

        # Completed unique scenarios
        unique_result = await self.db.execute(
            select(func.count(func.distinct(TrainingSession.scenario_id))).where(
                TrainingSession.employee_id == employee_id,
                TrainingSession.ai_score.isnot(None),
            )
        )
        unique_completed = unique_result.scalar() or 0

        return {
            "employee_id": employee_id,
            "total_sessions": stats.total_sessions or 0,
            "unique_scenarios_completed": unique_completed,
            "total_scenarios_available": total_scenarios,
            "completion_percentage": round(unique_completed / total_scenarios * 100, 1) if total_scenarios else 0,
            "average_score": round(float(stats.avg_score or 0), 1),
            "best_score": stats.best_score or 0,
            "passed_count": stats.passed or 0,
        }

    async def get_leaderboard(self, limit: int = 10) -> list[dict]:
        """Training scores leaderboard."""
        result = await self.db.execute(
            select(
                TrainingSession.employee_id,
                func.avg(TrainingSession.ai_score).label("avg_score"),
                func.count(TrainingSession.id).label("sessions"),
            ).where(TrainingSession.ai_score.isnot(None))
            .group_by(TrainingSession.employee_id)
            .order_by(func.avg(TrainingSession.ai_score).desc())
            .limit(limit)
        )
        return [
            {"employee_id": row.employee_id, "avg_score": round(float(row.avg_score), 1),
             "sessions": row.sessions, "rank": i + 1}
            for i, row in enumerate(result.all())
        ]

    def _get_scenario_by_id(self, scenario_id: str) -> dict | None:
        scenarios = _load_scenarios()
        for s in scenarios:
            if s["id"] == scenario_id:
                return s
        return None
