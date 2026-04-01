from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db
from app.services.audit_service import AuditService

router = APIRouter()


@router.get("/logs")
async def list_audit_logs(
    resource_type: str | None = None,
    resource_id: str | None = None,
    employee_id: int | None = None,
    action: str | None = None,
    start_date: datetime | None = None,
    end_date: datetime | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, le=200),
    db: AsyncSession = Depends(get_db),
):
    """List audit logs with filters. Admin only."""
    service = AuditService(db=db)
    logs, total = await service.get_audit_logs(
        resource_type=resource_type,
        resource_id=resource_id,
        employee_id=employee_id,
        action=action,
        start_date=start_date,
        end_date=end_date,
        page=page,
        page_size=page_size,
    )
    return {"logs": [_log_to_dict(log) for log in logs], "total": total, "page": page}


@router.get("/employee/{employee_id}/activity")
async def employee_activity(
    employee_id: int,
    days: int = Query(default=30, le=365),
    db: AsyncSession = Depends(get_db),
):
    """Get employee activity summary."""
    service = AuditService(db=db)
    return await service.get_employee_activity(employee_id, days)


def _log_to_dict(log) -> dict:
    return {
        "id": str(log.id),
        "employee_id": log.employee_id,
        "action": log.action,
        "resource_type": log.resource_type,
        "resource_id": log.resource_id,
        "old_values": log.old_values,
        "new_values": log.new_values,
        "status": log.status,
        "created_at": log.created_at.isoformat() if log.created_at else None,
    }
