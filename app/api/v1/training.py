"""Training API — Practice scenarios and evaluation for employees."""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db
from app.schemas.training import TrainingSubmitRequest
from app.services.training_service import TrainingService

router = APIRouter()


@router.get("/scenario")
async def get_next_scenario(
    employee_id: int = Query(...),
    difficulty: str | None = None,
    category: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    service = TrainingService(db)
    scenario = await service.get_next_scenario(employee_id, difficulty, category)
    if not scenario:
        return {"message": "No more scenarios available. Great job!"}
    # Start session
    session = await service.start_session(employee_id, scenario["id"])
    return {
        "session_id": str(session.id),
        "scenario": {
            "id": scenario["id"],
            "difficulty": scenario["difficulty"],
            "category": scenario["category"],
            "scenario_te": scenario["scenario_te"],
            "scenario_en": scenario["scenario_en"],
        },
    }


@router.post("/submit")
async def submit_response(
    request: TrainingSubmitRequest,
    db: AsyncSession = Depends(get_db),
):
    service = TrainingService(db)
    result = await service.evaluate_response(request.session_id, request.employee_response)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result


@router.get("/progress/{employee_id}")
async def get_progress(employee_id: int, db: AsyncSession = Depends(get_db)):
    service = TrainingService(db)
    return await service.get_employee_progress(employee_id)


@router.get("/leaderboard")
async def get_leaderboard(
    limit: int = Query(default=10, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
):
    service = TrainingService(db)
    return await service.get_leaderboard(limit)
