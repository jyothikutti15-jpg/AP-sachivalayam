from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db
from app.models.scheme import Scheme
from app.schemas.scheme import (
    BatchEligibilityCheckRequest,
    BatchEligibilityCheckResponse,
    EligibilityCheckRequest,
    EligibilityCheckResponse,
    SchemeResponse,
    SchemeSearchRequest,
    SchemeSearchResponse,
)
from app.services.scheme_advisor import SchemeAdvisor

router = APIRouter()


@router.get("/", response_model=list[SchemeResponse])
async def list_schemes(
    department: str | None = None,
    active_only: bool = True,
    limit: int = Query(default=50, le=200),
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
):
    """List all schemes with optional filters."""
    query = select(Scheme)
    if department:
        query = query.where(Scheme.department == department)
    if active_only:
        query = query.where(Scheme.is_active.is_(True))
    query = query.offset(offset).limit(limit)

    result = await db.execute(query)
    schemes = result.scalars().all()
    return schemes


@router.get("/{scheme_code}", response_model=SchemeResponse)
async def get_scheme(
    scheme_code: str,
    db: AsyncSession = Depends(get_db),
):
    """Get a single scheme by code."""
    result = await db.execute(select(Scheme).where(Scheme.scheme_code == scheme_code))
    scheme = result.scalar_one_or_none()
    if not scheme:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Scheme not found")
    return scheme


@router.post("/search", response_model=SchemeSearchResponse)
async def search_schemes(
    request: SchemeSearchRequest,
    db: AsyncSession = Depends(get_db),
):
    """Semantic search over schemes using RAG."""
    advisor = SchemeAdvisor(db=db)
    result = await advisor.search(
        query=request.query,
        department=request.department,
        language=request.language,
    )
    return result


@router.post("/eligibility-check", response_model=EligibilityCheckResponse)
async def check_eligibility(
    request: EligibilityCheckRequest,
    db: AsyncSession = Depends(get_db),
):
    """Check citizen eligibility for a scheme."""
    advisor = SchemeAdvisor(db=db)
    result = await advisor.check_eligibility(
        scheme_code=request.scheme_code,
        citizen_details=request.citizen_details,
    )
    return result


@router.post("/eligibility-check/batch", response_model=BatchEligibilityCheckResponse)
async def check_eligibility_batch(
    request: BatchEligibilityCheckRequest,
    db: AsyncSession = Depends(get_db),
):
    """Check eligibility for up to 50 citizen-scheme pairs in one call.

    All LLM checks run concurrently — significantly faster than calling
    /eligibility-check in a loop. Partial failures (unknown scheme or LLM
    error for one item) are surfaced per-result without failing the whole batch.
    """
    if len(request.items) == 0:
        raise HTTPException(status_code=422, detail="items list must not be empty")
    if len(request.items) > 50:
        raise HTTPException(status_code=422, detail="Batch size limit is 50 items")

    advisor = SchemeAdvisor(db=db)
    return await advisor.check_eligibility_batch(request.items)
