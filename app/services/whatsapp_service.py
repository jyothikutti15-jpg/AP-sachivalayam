import httpx
import structlog

from app.config import get_settings

logger = structlog.get_logger()
settings = get_settings()


class WhatsAppService:
    """Client for WhatsApp Business Cloud API."""

    def __init__(self):
        self.api_url = f"{settings.whatsapp_api_url}/{settings.whatsapp_phone_number_id}/messages"
        self.headers = {
            "Authorization": f"Bearer {settings.whatsapp_access_token}",
            "Content-Type": "application/json",
        }

    async def send_text(self, to: str, body: str) -> dict:
        """Send a text message."""
        payload = {
            "messaging_product": "whatsapp",
            "to": to,
            "type": "text",
            "text": {"body": body},
        }
        return await self._send(payload)

    async def send_buttons(self, to: str, body: str, buttons: list[dict]) -> dict:
        """Send interactive button message (max 3 buttons)."""
        button_list = [
            {"type": "reply", "reply": {"id": b["id"], "title": b["title"][:20]}}
            for b in buttons[:3]
        ]
        payload = {
            "messaging_product": "whatsapp",
            "to": to,
            "type": "interactive",
            "interactive": {
                "type": "button",
                "body": {"text": body},
                "action": {"buttons": button_list},
            },
        }
        return await self._send(payload)

    async def send_list(
        self, to: str, body: str, button_text: str, sections: list[dict]
    ) -> dict:
        """Send interactive list message (up to 10 items)."""
        payload = {
            "messaging_product": "whatsapp",
            "to": to,
            "type": "interactive",
            "interactive": {
                "type": "list",
                "body": {"text": body},
                "action": {
                    "button": button_text[:20],
                    "sections": sections,
                },
            },
        }
        return await self._send(payload)

    async def send_document(self, to: str, document_url: str, caption: str, filename: str) -> dict:
        """Send a document (PDF form)."""
        payload = {
            "messaging_product": "whatsapp",
            "to": to,
            "type": "document",
            "document": {
                "link": document_url,
                "caption": caption,
                "filename": filename,
            },
        }
        return await self._send(payload)

    async def download_media(self, media_id: str) -> bytes:
        """Download media (voice note) from WhatsApp CDN."""
        # Step 1: Get media URL
        media_url_endpoint = f"{settings.whatsapp_api_url}/{media_id}"
        async with httpx.AsyncClient() as client:
            resp = await client.get(media_url_endpoint, headers=self.headers)
            resp.raise_for_status()
            media_url = resp.json().get("url")

            # Step 2: Download the actual media
            media_resp = await client.get(media_url, headers=self.headers)
            media_resp.raise_for_status()
            return media_resp.content

    async def _send(self, payload: dict) -> dict:
        """Send a message via WhatsApp Business API."""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.api_url,
                    json=payload,
                    headers=self.headers,
                    timeout=30,
                )
                response.raise_for_status()
                result = response.json()
                logger.info(
                    "WhatsApp message sent",
                    to=payload.get("to", "")[-4:],
                    type=payload.get("type"),
                )
                return result
        except httpx.HTTPStatusError as e:
            logger.error(
                "WhatsApp API error",
                status=e.response.status_code,
                body=e.response.text,
            )
            raise
        except Exception as e:
            logger.error("WhatsApp send failed", error=str(e))
            raise
