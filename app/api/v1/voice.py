from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.dependencies import get_db
from app.schemas.voice import TranscriptionResponse
from app.services.voice_pipeline import VoicePipeline

router = APIRouter()

# Audio MIME types accepted for transcription.
# Covers WhatsApp voice notes (ogg/opus) and common upload formats.
_ALLOWED_AUDIO_TYPES = {
    "audio/ogg",
    "audio/mpeg",
    "audio/mp4",
    "audio/wav",
    "audio/wave",
    "audio/x-wav",
    "audio/aac",
    "audio/webm",
    "audio/flac",
    "audio/x-m4a",
}

_CHUNK = 1024 * 1024  # 1 MB read chunks


@router.post("/transcribe", response_model=TranscriptionResponse)
async def transcribe_audio(
    file: UploadFile = File(...),
    language: str = "te",
    db: AsyncSession = Depends(get_db),
):
    """Transcribe an audio file to Telugu/English text.

    Limits:
    - Max file size: VOICE_MAX_FILE_SIZE_MB (default 25 MB)
    - Accepted types: ogg, mp3, mp4, wav, aac, webm, flac, m4a
    """
    settings = get_settings()
    max_bytes = settings.voice_max_file_size_mb * 1024 * 1024

    # Content-type check (browsers/WhatsApp set this; defence-in-depth only).
    content_type = (file.content_type or "").split(";")[0].strip().lower()
    if content_type and content_type not in _ALLOWED_AUDIO_TYPES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Unsupported media type '{content_type}'. Upload an audio file.",
        )

    # Read in 1 MB chunks so we never buffer an oversized file in memory.
    audio_bytes = b""
    while chunk := await file.read(_CHUNK):
        audio_bytes += chunk
        if len(audio_bytes) > max_bytes:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=(
                    f"Audio file exceeds the {settings.voice_max_file_size_mb} MB limit. "
                    "Please send a shorter voice note."
                ),
            )

    pipeline = VoicePipeline()
    result = await pipeline.transcribe(
        audio_data=audio_bytes,
        language=language,
        filename=file.filename or "audio.ogg",
    )
    return result
