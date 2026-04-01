from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db
from app.services.performance_service import PerformanceService

router = APIRouter()


@router.get("/employee/{employee_id}")
async def get_employee_performance(
    employee_id: int,
    period_type: str = Query(default="weekly", pattern="^(daily|weekly|monthly)$"),
    periods: int = Query(default=4, le=52),
    db: AsyncSession = Depends(get_db),
):
    """Get individual employee performance metrics."""
    service = PerformanceService(db=db)
    return await service.get_employee_performance(employee_id, period_type, periods)


@router.get("/team/{secretariat_id}")
async def get_team_performance(
    secretariat_id: int,
    period_type: str = Query(default="weekly", pattern="^(daily|weekly|monthly)$"),
    db: AsyncSession = Depends(get_db),
):
    """Get team performance for a secretariat."""
    service = PerformanceService(db=db)
    return await service.get_team_performance(secretariat_id, period_type)


@router.get("/leaderboard")
async def get_leaderboard(
    metric: str = Query(
        default="grievances_resolved",
        description="Metric to rank by",
    ),
    period_type: str = Query(default="monthly", pattern="^(daily|weekly|monthly)$"),
    limit: int = Query(default=10, le=50),
    db: AsyncSession = Depends(get_db),
):
    """Get employee leaderboard ranked by a specific metric."""
    service = PerformanceService(db=db)
    return await service.get_leaderboard(metric, period_type, limit)
