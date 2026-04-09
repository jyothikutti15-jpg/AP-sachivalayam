"""
API endpoints for GO/Circular Knowledge Base (Feature 9).

Employees can search government orders and circulars, get AI-powered
summaries, and stay updated on scheme policy changes.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db
from app.schemas.circular import (
    CircularCreate,
    CircularResponse,
    CircularSearchRequest,
    CircularSearchResponse,
    CircularSummaryRequest,
)
from app.services.circular_service import CircularService

router = APIRouter()


@router.get("/", response_model=list[CircularResponse])
async def list_circulars(
    department: str | None = None,
    limit: int = Query(default=20, le=100),
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
):
    """List recent government orders and circulars."""
    service = CircularService(db=db)
    circulars = await service.list_recent(
        department=department, limit=limit, offset=offset
    )
    return circulars


@router.get("/reference/{reference_number}", response_model=CircularResponse)
async def get_circular_by_reference(
    reference_number: str,
    db: AsyncSession = Depends(get_db),
):
    """Get a specific GO/circular by its reference number."""
    service = CircularService(db=db)
    circular = await service.get_by_reference(reference_number)
    if not circular:
        raise HTTPException(status_code=404, detail="Circular not found")
    return circular


@router.post("/search", response_model=CircularSearchResponse)
async def search_circulars(
    request: CircularSearchRequest,
    db: AsyncSession = Depends(get_db),
):
    """Search circulars with AI-powered answer generation.

    Supports searching by keyword, department, scheme code, and date range.
    Returns an AI-generated answer citing specific GO numbers.
    """
    service = CircularService(db=db)
    return await service.search(
        query=request.query,
        department=request.department,
        scheme_code=request.scheme_code,
        from_date=request.from_date,
        to_date=request.to_date,
        language=request.language,
    )


@router.post("/", response_model=CircularResponse, status_code=201)
async def create_circular(
    data: CircularCreate,
    db: AsyncSession = Depends(get_db),
):
    """Add a new GO/circular to the knowledge base."""
    service = CircularService(db=db)
    circular = await service.create_circular(data)
    await db.commit()
    return circular


@router.post("/summarize")
async def summarize_circular(
    request: CircularSummaryRequest,
    db: AsyncSession = Depends(get_db),
):
    """Auto-summarize a GO/circular using AI.

    Provide either a reference_number (to look up existing circular)
    or raw content_te/content_en text to summarize.
    """
    service = CircularService(db=db)

    content = request.content_te or request.content_en

    # If reference number provided, look up the circular
    if request.reference_number and not content:
        circular = await service.get_by_reference(request.reference_number)
        if not circular:
            raise HTTPException(status_code=404, detail="Circular not found")
        content = circular.content_te or circular.content_en

    if not content:
        raise HTTPException(
            status_code=422,
            detail="Provide either reference_number or content_te/content_en",
        )

    return await service.auto_summarize(content)
