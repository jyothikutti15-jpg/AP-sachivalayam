from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db
from app.schemas.task import (
    DailyPlanResponse,
    TaskCreateRequest,
    TaskResponse,
    TaskUpdateRequest,
    WorkloadSummaryResponse,
)
from app.services.task_service import TaskService

router = APIRouter()


@router.post("/", response_model=TaskResponse, status_code=201)
async def create_task(
    request: TaskCreateRequest,
    employee_id: int = Query(..., description="Employee ID"),
    secretariat_id: int | None = None,
    db: AsyncSession = Depends(get_db),
):
    """Create a new task for an employee."""
    service = TaskService(db=db)
    return await service.create_task(
        request=request,
        employee_id=employee_id,
        secretariat_id=secretariat_id,
    )


@router.get("/daily-plan", response_model=DailyPlanResponse)
async def get_daily_plan(
    employee_id: int = Query(..., description="Employee ID"),
    plan_date: date | None = None,
    db: AsyncSession = Depends(get_db),
):
    """Get AI-powered daily task prioritization plan."""
    service = TaskService(db=db)
    return await service.generate_daily_plan(
        employee_id=employee_id,
        plan_date=plan_date,
    )


@router.get("/", response_model=list[TaskResponse])
async def list_tasks(
    employee_id: int = Query(..., description="Employee ID"),
    status: str | None = None,
    department: str | None = None,
    due_date: date | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, le=200),
    db: AsyncSession = Depends(get_db),
):
    """List tasks for an employee with filters."""
    service = TaskService(db=db)
    tasks, total = await service.list_tasks(
        employee_id=employee_id,
        status=status,
        department=department,
        due_date=due_date,
        page=page,
        page_size=page_size,
    )
    return tasks


@router.get("/{task_id}", response_model=TaskResponse)
async def get_task(
    task_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Get a single task by ID."""
    service = TaskService(db=db)
    result = await service.get_task(task_id)
    if not result:
        raise HTTPException(status_code=404, detail="Task not found")
    return result


@router.patch("/{task_id}", response_model=TaskResponse)
async def update_task(
    task_id: UUID,
    request: TaskUpdateRequest,
    employee_id: int = Query(..., description="Employee ID"),
    db: AsyncSession = Depends(get_db),
):
    """Update task status, priority, or details."""
    service = TaskService(db=db)
    result = await service.update_task(task_id, request, employee_id)
    if not result:
        raise HTTPException(status_code=404, detail="Task not found")
    return result


@router.post("/{task_id}/start", response_model=TaskResponse)
async def start_task(
    task_id: UUID,
    employee_id: int = Query(..., description="Employee ID"),
    db: AsyncSession = Depends(get_db),
):
    """Mark a task as in-progress."""
    service = TaskService(db=db)
    result = await service.update_task(
        task_id,
        TaskUpdateRequest(status="in_progress"),
        employee_id,
    )
    if not result:
        raise HTTPException(status_code=404, detail="Task not found")
    return result


@router.post("/{task_id}/complete", response_model=TaskResponse)
async def complete_task(
    task_id: UUID,
    employee_id: int = Query(..., description="Employee ID"),
    actual_minutes: int | None = None,
    db: AsyncSession = Depends(get_db),
):
    """Mark a task as completed."""
    service = TaskService(db=db)
    result = await service.update_task(
        task_id,
        TaskUpdateRequest(status="completed", actual_minutes=actual_minutes),
        employee_id,
    )
    if not result:
        raise HTTPException(status_code=404, detail="Task not found")
    return result


@router.get("/workload/summary", response_model=WorkloadSummaryResponse)
async def workload_summary(
    employee_id: int = Query(..., description="Employee ID"),
    summary_date: date | None = None,
    db: AsyncSession = Depends(get_db),
):
    """Get workload summary for an employee."""
    service = TaskService(db=db)
    return await service.get_workload_summary(
        employee_id=employee_id,
        summary_date=summary_date,
    )


@router.post("/bulk-create", status_code=201)
async def bulk_create_tasks(
    tasks: list[TaskCreateRequest],
    employee_id: int = Query(...),
    secretariat_id: int | None = None,
    db: AsyncSession = Depends(get_db),
):
    """Bulk create tasks (max 100 per request)."""
    if len(tasks) > 100:
        raise HTTPException(400, "Max 100 tasks per bulk request")
    service = TaskService(db=db)
    results = {"created": 0, "failed": 0, "errors": []}
    for i, req in enumerate(tasks):
        try:
            await service.create_task(req, employee_id, secretariat_id)
            results["created"] += 1
        except Exception as e:
            results["failed"] += 1
            results["errors"].append({"index": i, "error": str(e)})
    return results


@router.get("/export/csv")
async def export_tasks_csv(
    employee_id: int | None = None,
    status: str | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
    db: AsyncSession = Depends(get_db),
):
    """Export tasks as CSV file."""
    from app.services.export_service import ExportService
    service = ExportService(db=db)
    csv_data = await service.export_tasks_csv(employee_id, status, start_date, end_date)
    return StreamingResponse(
        iter([csv_data]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=tasks_export.csv"},
    )
