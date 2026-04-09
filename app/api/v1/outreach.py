"""Outreach API — Proactive scheme outreach endpoints."""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db
from app.models.beneficiary import Beneficiary
from app.schemas.outreach import (
    BeneficiaryCreateRequest,
    BeneficiaryEligibleSchemesResponse,
    BeneficiaryResponse,
    OutreachListResponse,
    OutreachScanResponse,
    OutreachStatusUpdateResponse,
)
from app.services.outreach_engine import OutreachEngine

router = APIRouter()


@router.post("/outreach/scan/{secretariat_id}", response_model=OutreachScanResponse)
async def scan_secretariat(
    secretariat_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Trigger outreach scan for a secretariat — matches beneficiaries to schemes."""
    engine = OutreachEngine(db=db)
    matches = await engine.scan_secretariat(secretariat_id)
    return OutreachScanResponse(
        secretariat_id=secretariat_id,
        matches_found=len(matches),
        matches=matches,
    )


@router.get("/outreach/{secretariat_id}", response_model=OutreachListResponse)
async def get_outreach_list(
    secretariat_id: int,
    scheme_code: str | None = None,
    status: str | None = None,
    limit: int = Query(default=50, le=200),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    """Get outreach list for a secretariat with optional filters."""
    engine = OutreachEngine(db=db)
    items, total = await engine.get_outreach_list(
        secretariat_id=secretariat_id,
        scheme_code=scheme_code,
        status=status,
        limit=limit,
        offset=offset,
    )
    return OutreachListResponse(items=items, total=total, limit=limit, offset=offset)


@router.get("/outreach/beneficiary/{beneficiary_id}/eligible", response_model=BeneficiaryEligibleSchemesResponse)
async def get_eligible_schemes(
    beneficiary_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Find all schemes a beneficiary is eligible for."""
    engine = OutreachEngine(db=db)
    matches = await engine.scan_beneficiary(beneficiary_id)
    return BeneficiaryEligibleSchemesResponse(
        beneficiary_id=beneficiary_id,
        eligible_schemes=matches,
    )


@router.patch("/outreach/{outreach_id}/notify", response_model=OutreachStatusUpdateResponse)
async def mark_notified(
    outreach_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Mark an outreach record as notified."""
    engine = OutreachEngine(db=db)
    result = await engine.mark_notified(outreach_id)
    if not result:
        raise HTTPException(status_code=404, detail="Outreach record not found")
    return OutreachStatusUpdateResponse(**result)


@router.patch("/outreach/{outreach_id}/applied", response_model=OutreachStatusUpdateResponse)
async def mark_applied(
    outreach_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Mark an outreach record as applied."""
    engine = OutreachEngine(db=db)
    result = await engine.mark_applied(outreach_id)
    if not result:
        raise HTTPException(status_code=404, detail="Outreach record not found")
    return OutreachStatusUpdateResponse(**result)


@router.post("/beneficiaries", response_model=BeneficiaryResponse, status_code=201)
async def create_beneficiary(
    request: BeneficiaryCreateRequest,
    db: AsyncSession = Depends(get_db),
):
    """Create a new beneficiary record."""
    beneficiary = Beneficiary(
        aadhaar_hash=request.aadhaar_hash,
        phone_number=request.phone_number,
        name_te=request.name_te,
        name_en=request.name_en,
        age=request.age,
        gender=request.gender,
        caste_category=request.caste_category,
        annual_income=request.annual_income,
        ration_card_type=request.ration_card_type,
        district=request.district,
        mandal=request.mandal,
        secretariat_id=request.secretariat_id,
        is_disabled=request.is_disabled,
        disability_percentage=request.disability_percentage,
        occupation=request.occupation,
        land_acres_wet=request.land_acres_wet,
        land_acres_dry=request.land_acres_dry,
        num_children=request.num_children,
        is_govt_employee=request.is_govt_employee,
        is_income_tax_payer=request.is_income_tax_payer,
        owns_four_wheeler=request.owns_four_wheeler,
        electricity_units=request.electricity_units,
        schemes_enrolled=request.schemes_enrolled,
        opt_out=request.opt_out,
    )
    db.add(beneficiary)
    await db.flush()
    await db.refresh(beneficiary)
    return beneficiary


@router.get("/beneficiaries/{secretariat_id}", response_model=list[BeneficiaryResponse])
async def list_beneficiaries(
    secretariat_id: int,
    limit: int = Query(default=50, le=200),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    """List beneficiaries in a secretariat."""
    result = await db.execute(
        select(Beneficiary)
        .where(Beneficiary.secretariat_id == secretariat_id)
        .order_by(Beneficiary.id)
        .offset(offset)
        .limit(limit)
    )
    return result.scalars().all()
