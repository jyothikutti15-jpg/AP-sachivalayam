from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db
from app.models.scheme import Scheme
from app.schemas.scheme import EligibilityCheckRequest, EligibilityCheckResponse, SchemeResponse, SchemeSearchRequest, SchemeSearchResponse
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
