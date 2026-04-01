from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db
from app.models.form import FormSubmission, FormTemplate
from app.schemas.form import AutoFillRequest, AutoFillResponse, FormTemplateResponse
from app.services.form_filler import FormFiller

router = APIRouter()


@router.get("/templates", response_model=list[FormTemplateResponse])
async def list_templates(
    department: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    """List available form templates."""
    query = select(FormTemplate)
    if department:
        query = query.where(FormTemplate.department == department)
    result = await db.execute(query)
    return result.scalars().all()


@router.post("/auto-fill", response_model=AutoFillResponse)
async def auto_fill_form(
    request: AutoFillRequest,
    db: AsyncSession = Depends(get_db),
):
    """Generate a filled form from text/voice input."""
    filler = FormFiller(db=db)
    result = await filler.auto_fill(
        template_id=request.template_id,
        employee_id=request.employee_id,
        input_text=request.input_text,
        citizen_name=request.citizen_name,
    )
    return result


@router.get("/{submission_id}/pdf")
async def download_form_pdf(
    submission_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Download a generated form as PDF."""
    result = await db.execute(
        select(FormSubmission).where(FormSubmission.id == submission_id)
    )
    submission = result.scalar_one_or_none()
    if not submission:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Submission not found")

    if not submission.pdf_url:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="PDF not generated yet")

    from fastapi.responses import FileResponse
    return FileResponse(submission.pdf_url, media_type="application/pdf")


@router.post("/{submission_id}/submit-to-gsws")
async def submit_to_gsws(
    submission_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Push a completed form to GSWS portal."""
    from app.services.gsws_bridge import GSWSBridge

    bridge = GSWSBridge(db=db)
    result = await bridge.submit_form(submission_id=submission_id)
    return result
