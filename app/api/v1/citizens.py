"""Citizens API — Admin lookup for citizen records."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db
from app.models.citizen import Citizen
from app.schemas.citizen import CitizenResponse

router = APIRouter()


@router.get("/{phone}", response_model=CitizenResponse)
async def get_citizen_by_phone(phone: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Citizen).where(Citizen.phone_number == phone))
    citizen = result.scalar_one_or_none()
    if not citizen:
        raise HTTPException(status_code=404, detail="Citizen not found")
    return citizen


@router.get("/", response_model=list[CitizenResponse])
async def list_citizens(
    district: str | None = None,
    limit: int = 50,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
):
    query = select(Citizen)
    if district:
        query = query.where(Citizen.district == district)
    query = query.order_by(Citizen.created_at.desc()).offset(offset).limit(limit)
    result = await db.execute(query)
    return result.scalars().all()
