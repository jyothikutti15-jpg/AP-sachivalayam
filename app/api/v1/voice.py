from fastapi import APIRouter, Depends, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db
from app.schemas.voice import TranscriptionResponse
from app.services.voice_pipeline import VoicePipeline

router = APIRouter()


@router.post("/transcribe", response_model=TranscriptionResponse)
async def transcribe_audio(
    file: UploadFile = File(...),
    language: str = "te",
    db: AsyncSession = Depends(get_db),
):
    """Transcribe an audio file to Telugu/English text."""
    audio_bytes = await file.read()
    pipeline = VoicePipeline()
    result = await pipeline.transcribe(
        audio_data=audio_bytes,
        language=language,
        filename=file.filename or "audio.ogg",
    )
    return result
