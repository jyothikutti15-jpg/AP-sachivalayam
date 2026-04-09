"""Supervisor Dashboard API — Aggregate views for MPDO/Mandal/District officers."""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db
from app.services.supervisor_service import SupervisorService

router = APIRouter()


@router.get("/mandal/{mandal_name}/overview")
async def get_mandal_overview(
    mandal_name: str,
    days: int = Query(default=30, ge=1, le=365),
    db: AsyncSession = Depends(get_db),
):
    service = SupervisorService(db)
    return await service.get_mandal_overview(mandal_name, days)


@router.get("/mandal/{mandal_name}/secretariats")
async def get_secretariat_rankings(
    mandal_name: str,
    metric: str = Query(default="grievances_resolved"),
    limit: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    service = SupervisorService(db)
    return await service.get_secretariat_rankings(mandal_name, metric, limit)


@router.get("/district/{district_name}/overview")
async def get_district_overview(
    district_name: str,
    days: int = Query(default=30, ge=1, le=365),
    db: AsyncSession = Depends(get_db),
):
    service = SupervisorService(db)
    return await service.get_district_overview(district_name, days)


@router.get("/alerts/sla-breaches")
async def get_sla_breach_alerts(
    mandal: str | None = None,
    district: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    service = SupervisorService(db)
    alerts, total = await service.get_sla_breach_alerts(mandal, district, limit, offset)
    return {"alerts": alerts, "total": total}


@router.get("/alerts/low-performing")
async def get_low_performing(
    district: str = Query(...),
    threshold: float = Query(default=50.0, ge=0, le=100),
    db: AsyncSession = Depends(get_db),
):
    service = SupervisorService(db)
    return await service.get_low_performing_secretariats(district, threshold)


@router.get("/employee/{employee_id}/detail")
async def get_employee_detail(
    employee_id: int,
    db: AsyncSession = Depends(get_db),
):
    service = SupervisorService(db)
    result = await service.get_employee_detail(employee_id)
    if not result:
        raise HTTPException(status_code=404, detail="Employee not found")
    return result
