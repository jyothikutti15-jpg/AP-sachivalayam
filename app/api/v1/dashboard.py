from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db
from app.schemas.analytics import BurnoutReportResponse, SecretariatSummaryResponse, TimeSavedResponse
from app.services.analytics_service import AnalyticsService

router = APIRouter()


@router.get("/secretariat/{secretariat_id}/summary", response_model=SecretariatSummaryResponse)
async def secretariat_summary(
    secretariat_id: int,
    start_date: date = Query(...),
    end_date: date = Query(...),
    db: AsyncSession = Depends(get_db),
):
    """Get usage summary for a secretariat."""
    service = AnalyticsService(db=db)
    return await service.get_secretariat_summary(secretariat_id, start_date, end_date)


@router.get("/burnout-report", response_model=list[BurnoutReportResponse])
async def burnout_report(
    district: str | None = None,
    week_start: date = Query(...),
    db: AsyncSession = Depends(get_db),
):
    """Get burnout reduction metrics."""
    service = AnalyticsService(db=db)
    return await service.get_burnout_report(week_start=week_start, district=district)


@router.get("/time-saved", response_model=TimeSavedResponse)
async def time_saved(
    start_date: date = Query(...),
    end_date: date = Query(...),
    district: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    """Get total time saved across employees."""
    service = AnalyticsService(db=db)
    return await service.get_time_saved(start_date, end_date, district)


@router.get("/export")
async def export_report(
    start_date: date = Query(...),
    end_date: date = Query(...),
    format: str = Query(default="csv", regex="^(csv|pdf)$"),
    db: AsyncSession = Depends(get_db),
):
    """Export analytics data as CSV or PDF."""
    service = AnalyticsService(db=db)
    file_path = await service.export_report(start_date, end_date, format)

    from fastapi.responses import FileResponse
    media_type = "text/csv" if format == "csv" else "application/pdf"
    return FileResponse(file_path, media_type=media_type, filename=f"report.{format}")
