from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db
from app.schemas.grievance import (
    GrievanceAISuggestResponse,
    GrievanceCommentRequest,
    GrievanceCommentResponse,
    GrievanceCreateRequest,
    GrievanceListResponse,
    GrievanceResponse,
    GrievanceUpdateRequest,
)
from app.services.grievance_service import GrievanceService

router = APIRouter()


@router.post("/", response_model=GrievanceResponse, status_code=201)
async def file_grievance(
    request: GrievanceCreateRequest,
    employee_id: int = Query(..., description="Filing employee's ID"),
    secretariat_id: int | None = None,
    db: AsyncSession = Depends(get_db),
):
    """File a new citizen grievance."""
    service = GrievanceService(db=db)
    return await service.file_grievance(
        request=request,
        employee_id=employee_id,
        secretariat_id=secretariat_id,
    )


@router.get("/{grievance_id}", response_model=GrievanceResponse)
async def get_grievance(
    grievance_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Get grievance by ID."""
    service = GrievanceService(db=db)
    result = await service.get_grievance(grievance_id)
    if not result:
        raise HTTPException(status_code=404, detail="Grievance not found")
    return result


@router.get("/reference/{reference_number}", response_model=GrievanceResponse)
async def get_grievance_by_reference(
    reference_number: str,
    db: AsyncSession = Depends(get_db),
):
    """Get grievance by reference number (e.g., GRV-2026-0001)."""
    service = GrievanceService(db=db)
    result = await service.get_by_reference(reference_number)
    if not result:
        raise HTTPException(status_code=404, detail="Grievance not found")
    return result


@router.get("/", response_model=GrievanceListResponse)
async def list_grievances(
    employee_id: int | None = None,
    secretariat_id: int | None = None,
    status: str | None = None,
    category: str | None = None,
    priority: str | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, le=100),
    db: AsyncSession = Depends(get_db),
):
    """List grievances with filters."""
    service = GrievanceService(db=db)
    grievances, total = await service.list_grievances(
        employee_id=employee_id,
        secretariat_id=secretariat_id,
        status=status,
        category=category,
        priority=priority,
        page=page,
        page_size=page_size,
    )
    return GrievanceListResponse(
        grievances=grievances,
        total=total,
        page=page,
        page_size=page_size,
    )


@router.patch("/{grievance_id}", response_model=GrievanceResponse)
async def update_grievance(
    grievance_id: UUID,
    request: GrievanceUpdateRequest,
    employee_id: int = Query(..., description="Employee making the update"),
    db: AsyncSession = Depends(get_db),
):
    """Update grievance status, priority, assignment, or resolution."""
    service = GrievanceService(db=db)
    result = await service.update_grievance(grievance_id, request, employee_id)
    if not result:
        raise HTTPException(status_code=404, detail="Grievance not found")
    return result


@router.post("/{grievance_id}/comments", response_model=GrievanceCommentResponse, status_code=201)
async def add_comment(
    grievance_id: UUID,
    request: GrievanceCommentRequest,
    employee_id: int = Query(..., description="Commenting employee's ID"),
    db: AsyncSession = Depends(get_db),
):
    """Add a comment to a grievance."""
    service = GrievanceService(db=db)
    return await service.add_comment(
        grievance_id=grievance_id,
        employee_id=employee_id,
        comment_text=request.comment_text,
        comment_type=request.comment_type,
    )


@router.post("/ai-suggest", response_model=GrievanceAISuggestResponse)
async def ai_suggest_grievance(
    category: str,
    subject: str,
    description: str,
    db: AsyncSession = Depends(get_db),
):
    """Get AI suggestions for grievance routing, priority, and resolution."""
    service = GrievanceService(db=db)
    return await service.ai_suggest(
        category=category,
        subject=subject,
        description=description,
    )


@router.get("/stats/summary")
async def grievance_stats(
    secretariat_id: int | None = None,
    db: AsyncSession = Depends(get_db),
):
    """Get grievance statistics for dashboard."""
    service = GrievanceService(db=db)
    return await service.get_grievance_stats(secretariat_id)


@router.post("/bulk-create", status_code=201)
async def bulk_create_grievances(
    grievances: list[GrievanceCreateRequest],
    employee_id: int = Query(...),
    secretariat_id: int | None = None,
    db: AsyncSession = Depends(get_db),
):
    """Bulk create grievances (max 50 per request)."""
    if len(grievances) > 50:
        raise HTTPException(400, "Max 50 grievances per bulk request")
    service = GrievanceService(db=db)
    results = {"created": [], "failed": []}
    for i, req in enumerate(grievances):
        try:
            g = await service.file_grievance(req, employee_id, secretariat_id)
            results["created"].append(g.reference_number)
        except Exception as e:
            results["failed"].append({"index": i, "error": str(e)})
    return {
        "created_count": len(results["created"]),
        "failed_count": len(results["failed"]),
        "details": results,
    }


@router.get("/export/csv")
async def export_grievances_csv(
    secretariat_id: int | None = None,
    status: str | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
    db: AsyncSession = Depends(get_db),
):
    """Export grievances as CSV file."""
    from app.services.export_service import ExportService
    service = ExportService(db=db)
    csv_data = await service.export_grievances_csv(secretariat_id, status, start_date, end_date)
    return StreamingResponse(
        iter([csv_data]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=grievances_export.csv"},
    )
