"""
API endpoints for Document Checklist Generator (Feature 8).

Generates a personalized document checklist across all eligible schemes
given a citizen's profile — avoids repeat visits to the secretariat.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db
from app.schemas.checklist import CitizenProfile, DocumentChecklistResponse
from app.services.checklist_service import ChecklistService

router = APIRouter()


@router.post("/generate", response_model=DocumentChecklistResponse)
async def generate_checklist(
    citizen: CitizenProfile,
    db: AsyncSession = Depends(get_db),
):
    """Generate a personalized document checklist for a citizen.

    Given a citizen's profile (age, income, caste, ration card, etc.),
    checks eligibility across all active schemes and returns a consolidated
    list of documents needed — with common documents highlighted to avoid
    repeat collection.
    """
    service = ChecklistService(db=db)
    return await service.generate_checklist(citizen)
