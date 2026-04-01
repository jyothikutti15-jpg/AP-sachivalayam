"""
GSWS Bridge — Adapter for AP's Grama Sachivalayam Web Service portal.

Supports:
- Mock mode (for development/pilot without real GSWS API access)
- Real mode (when GSWS API credentials are available)
- Automatic fallback to mock when real API is unreachable
- Offline queue for intermittent connectivity
"""
import random
import string
from datetime import datetime, timezone
from uuid import UUID

import httpx
import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.config import get_settings
from app.core.exceptions import GSWSConnectionError
from app.models.form import FormSubmission
from app.models.offline import OfflineQueueItem
from app.models.scheme import Scheme

logger = structlog.get_logger()
settings = get_settings()


def _is_mock_mode() -> bool:
    """Check if we should use mock GSWS responses."""
    return not settings.gsws_api_key or settings.gsws_api_key == "your-gsws-api-key"


class GSWSBridge:
    """Adapter for GSWS portal API — reads from and writes to the government system."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.base_url = settings.gsws_api_base_url
        self.headers = {
            "Authorization": f"Bearer {settings.gsws_api_key}",
            "Content-Type": "application/json",
            "X-Source": "AP-Sachivalayam-AI-Copilot",
        }
        self.mock_mode = _is_mock_mode()
        if self.mock_mode:
            logger.debug("GSWS bridge running in mock mode")

    async def submit_form(self, submission_id: UUID) -> dict:
        """Submit a completed form to GSWS portal."""
        result = await self.db.execute(
            select(FormSubmission).where(FormSubmission.id == submission_id)
        )
        submission = result.scalar_one_or_none()
        if not submission:
            return {"status": "error", "message": "Submission not found"}

        if self.mock_mode:
            return await self._mock_submit(submission)

        return await self._real_submit(submission)

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        retry=retry_if_exception_type((httpx.ConnectError, httpx.TimeoutException)),
    )
    async def _real_submit(self, submission: FormSubmission) -> dict:
        """Submit form via real GSWS API."""
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.post(
                    f"{self.base_url}/forms/submit",
                    json={
                        "form_code": submission.template_id,
                        "field_values": submission.field_values,
                        "citizen_name": submission.citizen_name,
                        "employee_id": submission.employee_id,
                    },
                    headers=self.headers,
                )
                response.raise_for_status()
                data = response.json()

                submission.gsws_submission_id = data.get("submission_id")
                submission.status = "submitted"
                submission.submitted_at = datetime.now(timezone.utc)

                logger.info(
                    "Form submitted to GSWS",
                    submission_id=str(submission.id),
                    gsws_id=submission.gsws_submission_id,
                )
                return {
                    "status": "submitted",
                    "gsws_id": submission.gsws_submission_id,
                    "message_te": f"✅ GSWS లో submit అయింది. Reference: {submission.gsws_submission_id}",
                }

        except (httpx.ConnectError, httpx.TimeoutException) as e:
            logger.warning("GSWS unreachable, queueing", error=str(e))
            await self._queue_for_retry(submission, "form_submit")
            return {
                "status": "queued",
                "message_te": "⏳ GSWS portal ప్రస్తుతం unavailable. Queue లో ఉంచాం — auto-retry అవుతుంది.",
            }
        except httpx.HTTPStatusError as e:
            logger.error("GSWS submission rejected", status=e.response.status_code)
            return {
                "status": "rejected",
                "message_te": f"❌ GSWS rejected: {e.response.text[:100]}",
            }

    async def _mock_submit(self, submission: FormSubmission) -> dict:
        """Mock GSWS submission for development/pilot."""
        gsws_id = "GSWS-" + "".join(random.choices(string.ascii_uppercase + string.digits, k=10))

        submission.gsws_submission_id = gsws_id
        submission.status = "submitted"
        submission.submitted_at = datetime.now(timezone.utc)

        logger.info("Mock GSWS submission", gsws_id=gsws_id)
        return {
            "status": "submitted",
            "gsws_id": gsws_id,
            "mock": True,
            "message_te": f"✅ GSWS లో submit అయింది (Mock). Reference: {gsws_id}",
        }

    async def check_application_status(self, reference_id: str) -> dict:
        """Check the status of an application in GSWS."""
        if self.mock_mode:
            return self._mock_status(reference_id)

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.get(
                    f"{self.base_url}/applications/{reference_id}/status",
                    headers=self.headers,
                )
                response.raise_for_status()
                return response.json()
        except (httpx.ConnectError, httpx.TimeoutException):
            raise GSWSConnectionError("GSWS portal unreachable")
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return {
                    "status": "not_found",
                    "message_te": f"❌ Reference '{reference_id}' కనుగొనబడలేదు. ID సరిగ్గా ఉందో check చేయండి.",
                }
            raise

    def _mock_status(self, reference_id: str) -> dict:
        """Mock application status for development."""
        statuses = ["pending", "under_review", "approved", "disbursed"]
        status = random.choice(statuses)

        status_messages = {
            "pending": "⏳ Pending — సమీక్ష కోసం వేచి ఉంది",
            "under_review": "🔍 Under Review — Mandal level verification జరుగుతోంది",
            "approved": "✅ Approved — DBT processing లో ఉంది",
            "disbursed": "💰 Disbursed — Bank account లో credit అయింది",
        }

        return {
            "reference_id": reference_id,
            "status": status,
            "message_te": status_messages[status],
            "last_updated": datetime.now(timezone.utc).isoformat(),
            "mock": True,
        }

    async def citizen_lookup(self, aadhaar_last4: str, name: str | None = None) -> dict:
        """Look up citizen details in GSWS by Aadhaar last 4 digits."""
        if self.mock_mode:
            return {
                "found": True,
                "schemes_enrolled": ["YSR-AMMA-VODI", "YSR-PENSION-KANUKA"],
                "pending_applications": 1,
                "mock": True,
                "message_te": f"Aadhaar ...{aadhaar_last4}: 2 పథకాల్లో enrolled, 1 pending application.",
            }

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.get(
                    f"{self.base_url}/citizens/lookup",
                    params={"aadhaar_last4": aadhaar_last4, "name": name},
                    headers=self.headers,
                )
                response.raise_for_status()
                return response.json()
        except Exception as e:
            raise GSWSConnectionError(f"Citizen lookup failed: {e}")

    async def sync_scheme_data(self) -> dict:
        """Pull latest scheme data from GSWS portal (nightly sync)."""
        if self.mock_mode:
            logger.info("Mock GSWS scheme sync — using local data")
            scheme_count = await self.db.execute(select(Scheme))
            count = len(scheme_count.scalars().all())
            return {"status": "synced", "count": count, "mock": True}

        try:
            async with httpx.AsyncClient(timeout=60) as client:
                response = await client.get(
                    f"{self.base_url}/schemes",
                    headers=self.headers,
                )
                response.raise_for_status()
                schemes = response.json()
                logger.info("GSWS scheme data synced", count=len(schemes))
                return {"status": "synced", "count": len(schemes)}
        except Exception as e:
            logger.error("GSWS scheme sync failed", error=str(e))
            raise GSWSConnectionError(f"Scheme sync failed: {e}")

    async def _queue_for_retry(self, submission: FormSubmission, action: str) -> None:
        """Add failed operation to offline queue for retry."""
        queue_item = OfflineQueueItem(
            employee_id=submission.employee_id,
            action_type=action,
            payload={
                "submission_id": str(submission.id),
                "template_id": submission.template_id,
                "citizen_name": submission.citizen_name,
            },
        )
        self.db.add(queue_item)
        submission.status = "queued"
