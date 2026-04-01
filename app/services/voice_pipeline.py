"""
Voice Pipeline — Telugu voice processing for AP Sachivalayam.

Flow: WhatsApp voice note (OGG) → FFmpeg convert → Whisper STT → Post-process → Clean text
Supports: Sync (direct call) and Async (Celery worker for heavy loads)
"""
import os
import re
import subprocess
import tempfile
import uuid

import structlog

from app.config import get_settings
from app.core.security import AADHAAR_PATTERN, PHONE_PATTERN, strip_pii
from app.core.telugu import (
    fuzzy_match_scheme,
    normalize_telugu_text,
    telugu_to_arabic,
)
from app.schemas.voice import TranscriptionResponse

logger = structlog.get_logger()
settings = get_settings()

# Telugu domain vocabulary for Whisper initial_prompt (boosts accuracy)
WHISPER_TELUGU_PROMPT = (
    "ఆంధ్రప్రదేశ్ సచివాలయం గ్రామ పథకాలు అమ్మ ఒడి రైతు భరోసా ఆరోగ్యశ్రీ చేయూత "
    "కళ్యాణమస్తు విద్యా దీవెన వసతి దీవెన పెన్షన్ కానుక ఆసరా సున్నా వడ్డీ "
    "దరఖాస్తు అర్హత ప్రయోజనం ఫారం సమర్పించు ఆధార్ రేషన్ కార్డు "
    "మండలం జిల్లా గ్రామం సచివాలయం వలంటీర్ VRO "
    "పేరు వయస్సు ఆదాయం కులం వృత్తి చిరునామా "
    "నమస్కారం దయచేసి ధన్యవాదాలు"
)

# Telugu number words → digits mapping
TELUGU_NUMBER_WORDS = {
    "ఒకటి": "1", "రెండు": "2", "మూడు": "3", "నాలుగు": "4", "ఐదు": "5",
    "ఆరు": "6", "ఏడు": "7", "ఎనిమిది": "8", "తొమ్మిది": "9", "పది": "10",
    "ఇరవై": "20", "ముప్పై": "30", "నలభై": "40", "యాభై": "50",
    "అరవై": "60", "డెబ్భై": "70", "ఎనభై": "80", "తొంభై": "90",
    "వంద": "100", "నూరు": "100",
    "వెయ్యి": "1000", "వేయి": "1000",
    "లక్ష": "100000", "లక్షలు": "100000",
    "కోటి": "10000000",
}

# Whisper model singleton (avoid reloading on every call)
_whisper_model = None


def _get_whisper_model():
    """Lazy-load Whisper model."""
    global _whisper_model
    if _whisper_model is None:
        try:
            import whisper
            _whisper_model = whisper.load_model(
                settings.whisper_model_size,
                device=settings.whisper_device,
            )
            logger.info("Whisper model loaded", size=settings.whisper_model_size)
        except ImportError:
            logger.warning("Whisper not installed")
            return None
    return _whisper_model


class VoicePipeline:
    """Telugu voice processing: audio → transcription → clean text + entities."""

    async def transcribe(
        self,
        audio_data: bytes,
        language: str = "te",
        filename: str = "audio.ogg",
    ) -> TranscriptionResponse:
        """Full voice processing pipeline."""
        temp_dir = tempfile.mkdtemp()
        input_path = os.path.join(temp_dir, filename)
        wav_path = os.path.join(temp_dir, f"{uuid.uuid4()}.wav")

        with open(input_path, "wb") as f:
            f.write(audio_data)

        try:
            # 1. Convert to WAV 16kHz mono
            self._convert_audio(input_path, wav_path)

            # 2. Get audio duration
            duration = self._get_duration(wav_path)

            # 3. Transcribe with Whisper
            raw_text, confidence = self._whisper_transcribe(wav_path, language)

            if not raw_text:
                return TranscriptionResponse(
                    text="", language=language, confidence=0.0,
                    duration_seconds=duration,
                )

            # 4. Post-process Telugu text
            processed_text = self._post_process(raw_text)

            # 5. Extract entities
            entities = self._extract_entities(processed_text)

            logger.info(
                "Voice transcribed",
                language=language,
                duration=duration,
                confidence=confidence,
                text_length=len(processed_text),
                entities_found=len(entities),
            )

            return TranscriptionResponse(
                text=processed_text,
                language=language,
                confidence=confidence,
                duration_seconds=duration,
                entities=entities,
            )

        finally:
            for path in [input_path, wav_path]:
                if os.path.exists(path):
                    os.remove(path)
            if os.path.exists(temp_dir):
                try:
                    os.rmdir(temp_dir)
                except OSError:
                    pass

    def _convert_audio(self, input_path: str, output_path: str) -> None:
        """Convert any audio format to WAV 16kHz mono using ffmpeg."""
        cmd = [
            "ffmpeg", "-i", input_path,
            "-ar", "16000",       # 16kHz sample rate
            "-ac", "1",           # Mono
            "-sample_fmt", "s16", # 16-bit
            "-f", "wav",
            "-y", output_path,
        ]
        proc = subprocess.run(
            cmd, capture_output=True, timeout=30,
            # Suppress ffmpeg banner
            stdin=subprocess.DEVNULL,
        )
        if proc.returncode != 0:
            logger.error("FFmpeg failed", stderr=proc.stderr.decode()[:200])
            raise RuntimeError(f"Audio conversion failed: {proc.stderr.decode()[:100]}")

    def _get_duration(self, wav_path: str) -> float:
        """Get audio duration in seconds using ffprobe."""
        try:
            cmd = [
                "ffprobe", "-v", "quiet",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                wav_path,
            ]
            result = subprocess.run(cmd, capture_output=True, timeout=10)
            return float(result.stdout.decode().strip())
        except Exception:
            return 0.0

    def _whisper_transcribe(self, wav_path: str, language: str) -> tuple[str, float]:
        """Transcribe with Whisper, returns (text, confidence)."""
        model = _get_whisper_model()
        if model is None:
            return "", 0.0

        result = model.transcribe(
            wav_path,
            language=language,
            initial_prompt=WHISPER_TELUGU_PROMPT if language == "te" else None,
            fp16=(settings.whisper_device != "cpu"),
            verbose=False,
        )

        text = result.get("text", "").strip()

        # Calculate confidence from segments
        segments = result.get("segments", [])
        if segments:
            # avg_logprob is negative; closer to 0 = more confident
            avg_log_probs = [s.get("avg_logprob", -1.0) for s in segments]
            avg_log_prob = sum(avg_log_probs) / len(avg_log_probs)
            # Convert to 0-1 scale (rough approximation)
            confidence = min(1.0, max(0.0, 1.0 + avg_log_prob))
        else:
            confidence = 0.0

        return text, confidence

    def _post_process(self, text: str) -> str:
        """Clean up Whisper output for Telugu."""
        # 1. Normalize whitespace and Telugu text
        text = normalize_telugu_text(text)

        # 2. Convert Telugu digits to Arabic
        text = telugu_to_arabic(text)

        # 3. Convert Telugu number words to digits
        text = self._convert_number_words(text)

        # 4. Fix common Whisper Telugu errors
        text = self._fix_common_errors(text)

        # 5. Remove repeated phrases (Whisper hallucination)
        text = self._remove_repetitions(text)

        return text.strip()

    def _convert_number_words(self, text: str) -> str:
        """Convert Telugu number words to digits.
        'రెండు లక్షలు' → '200000', 'ముప్పై ఐదు' → '35'
        """
        # Handle compound numbers: "X లక్షలు" → X * 100000
        for word, value in [("లక్షలు", "00000"), ("లక్ష", "00000"),
                             ("వేలు", "000"), ("వెయ్యి", "000"), ("వేయి", "000")]:
            pattern = rf"(\d+)\s*{word}"
            text = re.sub(pattern, lambda m: str(int(m.group(1)) * int("1" + value)), text)

        # Handle simple number words
        for telugu_word, digit in TELUGU_NUMBER_WORDS.items():
            text = text.replace(telugu_word, digit)

        return text

    def _fix_common_errors(self, text: str) -> str:
        """Fix common Whisper transcription errors for Telugu domain."""
        replacements = {
            "amma vodi": "అమ్మ ఒడి",
            "rythu bharosa": "రైతు భరోసా",
            "aarogyasri": "ఆరోగ్యశ్రీ",
            "pension": "పెన్షన్",
            "aadhaar": "ఆధార్",
            "ration card": "రేషన్ కార్డు",
        }
        text_lower = text.lower()
        for english, telugu in replacements.items():
            if english in text_lower:
                text = re.sub(re.escape(english), telugu, text, flags=re.IGNORECASE)
        return text

    def _remove_repetitions(self, text: str) -> str:
        """Remove repeated phrases — a common Whisper hallucination."""
        words = text.split()
        if len(words) < 6:
            return text

        # Check if the second half is a repeat of the first half
        mid = len(words) // 2
        first_half = " ".join(words[:mid])
        second_half = " ".join(words[mid:mid + mid])

        if first_half == second_half:
            return first_half + " " + " ".join(words[mid + mid:])

        return text

    def _extract_entities(self, text: str) -> dict:
        """Extract structured entities from transcribed text."""
        entities: dict = {}

        # Scheme references
        scheme_code = fuzzy_match_scheme(text)
        if scheme_code:
            entities["scheme"] = scheme_code

        # Names (after common Telugu prefixes)
        name_patterns = re.findall(
            r"(?:పేరు|name|నా పేరు|citizen|పేషెంట్)\s*[:.]?\s*([^\d,।.]{2,30})",
            text, re.IGNORECASE,
        )
        if name_patterns:
            entities["names"] = [n.strip() for n in name_patterns]

        # Age
        age_match = re.search(r"(?:వయస్సు|age|years?)\s*[:.]?\s*(\d{1,3})", text, re.IGNORECASE)
        if age_match:
            age = int(age_match.group(1))
            if 0 < age < 150:
                entities["age"] = age

        # Income
        income_match = re.search(
            r"(?:ఆదాయం|income|salary|జీతం)\s*[:.]?\s*(?:₹?\s*)?(\d[\d,]*)",
            text, re.IGNORECASE,
        )
        if income_match:
            income_str = income_match.group(1).replace(",", "")
            entities["income"] = int(income_str)

        # Ration card type
        ration_match = re.search(
            r"(white|rice|pink|antyodaya|తెల్ల|బియ్యం|అంత్యోదయ)\s*(?:card|కార్డు)?",
            text, re.IGNORECASE,
        )
        if ration_match:
            card_map = {
                "white": "White", "తెల్ల": "White",
                "rice": "Rice", "బియ్యం": "Rice",
                "pink": "Pink",
                "antyodaya": "Antyodaya", "అంత్యోదయ": "Antyodaya",
            }
            entities["ration_card"] = card_map.get(ration_match.group(1).lower(), ration_match.group(1))

        # Caste/Community
        caste_match = re.search(
            r"\b(SC|ST|BC|OC|OBC|Minority|ముస్లిం|క్రైస్తవ)\b",
            text, re.IGNORECASE,
        )
        if caste_match:
            entities["caste"] = caste_match.group(1).upper()

        # Numbers (general — ages, amounts, counts)
        numbers = re.findall(r"\b\d{1,10}\b", text)
        if numbers:
            entities["numbers"] = numbers[:10]

        # Aadhaar detection (for warning, not storage)
        if AADHAAR_PATTERN.search(text):
            entities["aadhaar_detected"] = True

        # Phone detection
        if PHONE_PATTERN.search(text):
            entities["phone_detected"] = True

        return entities


class VoicePipelineAsync:
    """Async voice pipeline using Celery for heavy loads."""

    @staticmethod
    def dispatch_transcription(media_id: str, phone_number: str, session_id: str) -> str:
        """Dispatch voice transcription to Celery worker. Returns task ID."""
        from app.workers.voice_transcription import transcribe_voice_note
        task = transcribe_voice_note.delay(media_id, phone_number, session_id)
        return task.id

    @staticmethod
    def get_result(task_id: str) -> dict | None:
        """Check if async transcription is complete."""
        from app.workers.celery_app import celery_app
        result = celery_app.AsyncResult(task_id)
        if result.ready():
            return result.get()
        return None
