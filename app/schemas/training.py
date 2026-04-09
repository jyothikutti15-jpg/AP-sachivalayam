"""Training schemas — Request/response models for training API."""
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class TrainingScenarioResponse(BaseModel):
    id: str
    difficulty: str
    category: str
    scenario_te: str
    scenario_en: str


class TrainingSubmitRequest(BaseModel):
    session_id: str
    employee_response: str


class TrainingEvaluation(BaseModel):
    session_id: str
    score: int
    feedback_te: str
    feedback_en: str
    key_points_covered: list[bool]
    key_points_expected: list[str]


class TrainingProgress(BaseModel):
    employee_id: int
    total_sessions: int
    unique_scenarios_completed: int
    total_scenarios_available: int
    completion_percentage: float
    average_score: float
    best_score: int
    passed_count: int


class TrainingLeaderboardEntry(BaseModel):
    employee_id: int
    avg_score: float
    sessions: int
    rank: int


class TrainingSessionResponse(BaseModel):
    id: UUID
    employee_id: int
    scenario_id: str
    ai_score: int | None
    ai_feedback_te: str | None
    completed_at: datetime | None
    model_config = {"from_attributes": True}
