import hashlib
import hmac
import time

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.dependencies import get_db, redis_client
from app.schemas.whatsapp import WhatsAppWebhookPayload
from app.services.conversation_engine import ConversationEngine

logger = structlog.get_logger()
router = APIRouter()
settings = get_settings()

# Deduplication window (seconds) — WhatsApp may send the same webhook multiple times
DEDUP_WINDOW = 300  # 5 minutes


async def _is_duplicate(msg_id: str) -> bool:
    """Check if we've already processed this message ID (Redis dedup)."""
    try:
        key = f"wa_msg:{msg_id}"
        exists = await redis_client.get(key)
        if exists:
            return True
        await redis_client.setex(key, DEDUP_WINDOW, "1")
        return False
    except Exception:
        # If Redis is down, process anyway (better to double-process than miss)
        return False


def _verify_signature(request_body: bytes, signature: str) -> bool:
    """Verify WhatsApp webhook signature using HMAC-SHA256."""
    if not settings.whatsapp_verify_token:
        return True  # Skip verification in development

    expected = hmac.new(
        settings.whatsapp_verify_token.encode(),
        request_body,
        hashlib.sha256,
    ).hexdigest()

    return hmac.compare_digest(f"sha256={expected}", signature)


@router.get("/webhook")
async def verify_webhook(
    hub_mode: str = Query(alias="hub.mode", default=""),
    hub_verify_token: str = Query(alias="hub.verify_token", default=""),
    hub_challenge: str = Query(alias="hub.challenge", default=""),
):
    """WhatsApp webhook verification handshake (Meta Cloud API)."""
    if hub_mode == "subscribe" and hub_verify_token == settings.whatsapp_verify_token:
        logger.info("WhatsApp webhook verified")
        return int(hub_challenge)
    raise HTTPException(status_code=403, detail="Verification failed")


@router.post("/webhook")
async def receive_message(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Handle incoming WhatsApp messages.

    Flow: Verify → Deduplicate → Parse → Route to ConversationEngine → Respond
    """
    raw_body = await request.body()

    # 1. Verify webhook signature (production only)
    if settings.is_production:
        signature = request.headers.get("x-hub-signature-256", "")
        if not _verify_signature(raw_body, signature):
            logger.warning("Invalid webhook signature")
            raise HTTPException(status_code=401, detail="Invalid signature")

    # 2. Parse payload
    try:
        body = await request.json()
        payload = WhatsAppWebhookPayload.model_validate(body)
    except Exception:
        logger.warning("Invalid webhook payload")
        return {"status": "ok"}

    start_time = time.time()

    # 3. Process each message entry
    for entry in payload.entry:
        for change in entry.changes:
            if change.field != "messages":
                continue

            value = change.value
            messages = value.get("messages", [])
            contacts = value.get("contacts", [])
            statuses = value.get("statuses", [])

            # Handle delivery status updates (read receipts, etc.)
            if statuses and not messages:
                for status in statuses:
                    logger.debug(
                        "Delivery status",
                        msg_id=status.get("id"),
                        status=status.get("status"),
                    )
                continue

            for msg in messages:
                phone = msg.get("from", "")
                msg_type = msg.get("type", "text")
                msg_id = msg.get("id", "")
                timestamp = msg.get("timestamp", "")

                # 4. Deduplicate (WhatsApp retries on slow responses)
                if await _is_duplicate(msg_id):
                    logger.debug("Duplicate message skipped", msg_id=msg_id)
                    continue

                # 5. Extract content based on message type
                text_content = ""
                media_id = None
                interactive_id = None

                if msg_type == "text":
                    text_content = msg.get("text", {}).get("body", "")

                elif msg_type == "audio":
                    media_id = msg.get("audio", {}).get("id")

                elif msg_type == "image":
                    media_id = msg.get("image", {}).get("id")
                    text_content = msg.get("image", {}).get("caption", "")

                elif msg_type == "document":
                    media_id = msg.get("document", {}).get("id")
                    text_content = msg.get("document", {}).get("caption", "")

                elif msg_type == "interactive":
                    interactive = msg.get("interactive", {})
                    itype = interactive.get("type", "")
                    if itype == "button_reply":
                        reply = interactive.get("button_reply", {})
                        text_content = reply.get("title", "")
                        interactive_id = reply.get("id", "")
                    elif itype == "list_reply":
                        reply = interactive.get("list_reply", {})
                        text_content = reply.get("title", "")
                        interactive_id = reply.get("id", "")

                elif msg_type == "location":
                    loc = msg.get("location", {})
                    text_content = f"Location: {loc.get('latitude')}, {loc.get('longitude')}"

                elif msg_type == "contacts":
                    # Ignore contact shares
                    continue

                # 6. Get contact name
                contact_name = ""
                for contact in contacts:
                    if contact.get("wa_id") == phone:
                        contact_name = contact.get("profile", {}).get("name", "")
                        break

                logger.info(
                    "Incoming message",
                    phone=phone[-4:],
                    type=msg_type,
                    msg_id=msg_id,
                    text_preview=text_content[:50] if text_content else "[media]",
                )

                # 7. Process through conversation engine
                try:
                    engine = ConversationEngine(db=db)
                    await engine.handle_message(
                        phone_number=phone,
                        message_type=msg_type,
                        text_content=text_content,
                        media_id=media_id,
                        contact_name=contact_name,
                        interactive_id=interactive_id,
                    )
                except Exception as e:
                    logger.error(
                        "Message processing failed",
                        phone=phone[-4:],
                        msg_id=msg_id,
                        error=str(e),
                    )
                    # Send error message to user
                    from app.services.whatsapp_service import WhatsAppService
                    try:
                        wa = WhatsAppService()
                        await wa.send_text(
                            phone,
                            "క్షమించండి, సాంకేతిక సమస్య. దయచేసి కొద్దిసేపట్లో మళ్ళీ ప్రయత్నించండి. 🙏"
                        )
                    except Exception:
                        pass  # Don't fail the webhook on error notification failure

    elapsed_ms = int((time.time() - start_time) * 1000)
    logger.info("Webhook processed", elapsed_ms=elapsed_ms)

    # Always return 200 to WhatsApp (prevents retries)
    return {"status": "ok"}
