"""
Conversation Engine — The brain of the AP Sachivalayam AI Copilot.

Receives messages from WhatsApp, detects intent, maintains conversation context,
routes to appropriate services, and generates Telugu responses.
"""
import time
import uuid
from datetime import datetime, timedelta, timezone

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_employee_by_phone
from app.core.telugu import detect_language, fuzzy_match_scheme, normalize_telugu_text
from app.dependencies import redis_client
from app.models.interaction import ChatSession, Message
from app.models.user import Employee
from app.services.llm_service import LLMRouter
from app.services.scheme_advisor import SchemeAdvisor
from app.services.whatsapp_service import WhatsAppService

logger = structlog.get_logger()

# Session timeout — start a new session after 30 min of inactivity
SESSION_TIMEOUT = timedelta(minutes=30)

# Max conversation history to include in LLM context
MAX_HISTORY_MESSAGES = 10

# Intent keywords for fast classification
INTENT_KEYWORDS = {
    "scheme_query": [
        "పథకం", "scheme", "eligibility", "అర్హత", "ప్రయోజనం", "benefit",
        "amma vodi", "అమ్మ ఒడి", "rythu bharosa", "రైతు భరోసా", "aarogyasri",
        "ఆరోగ్యశ్రీ", "pension", "పెన్షన్", "cheyutha", "చేయూత", "documents",
        "డాక్యుమెంట్స్", "ఎంత", "how much", "ఎప్పుడు", "when",
    ],
    "eligibility_check": [
        "అర్హత ఉందా", "eligible", "qualify", "check eligibility",
        "అర్హత తనిఖీ", "వర్తిస్తుందా", "applies",
    ],
    "form_help": [
        "form", "ఫారం", "fill", "నింపు",
        "apply", "submit", "సమర్పించు", "pdf", "దరఖాస్తు నింపు",
    ],
    "status_check": [
        "status", "స్థితి", "pending", "approved", "rejected", "ఆమోదం",
        "track", "ట్రాక్", "ఎక్కడ ఉంది", "దరఖాస్తు స్థితి", "application status",
    ],
    "greeting": [
        "hi", "hello", "నమస్కారం", "నమస్తే", "హలో", "hey",
    ],
    "help": [
        "help", "సహాయం", "ఏం చేయగలవు", "what can you do", "menu",
        "options", "ఎలా", "how to",
    ],
    "thanks": [
        "thanks", "ధన్యవాదాలు", "thank you", "థాంక్స్", "బాగుంది",
        "great", "perfect",
    ],
    "grievance": [
        "grievance", "ఫిర్యాదు", "complaint", "ఫిర్యాద", "సమస్య", "problem",
        "issue", "report issue", "నివేదిక", "escalate", "ఎస్కలేట్",
        "resolve", "పరిష్కారం", "GRV", "grv",
    ],
    "task_query": [
        "task", "టాస్క్", "tasks", "పని", "daily plan", "రోజు plan",
        "what next", "ఏం చేయాలి", "workload", "పని భారం", "prioritize",
        "ప్రాధాన్యత", "pending work", "pending పని", "schedule", "complete task",
        "task done", "పని అయింది",
    ],
    "language_switch": [
        "switch to english", "english lo", "ఇంగ్లీష్ లో", "english please",
        "switch to telugu", "telugu lo", "తెలుగు లో", "telugu please",
        "change language", "భాష మార్చు",
    ],
}

# Interactive button/list IDs for routing
INTERACTIVE_ACTIONS = {
    "scheme_list": "show_scheme_list",
    "form_help": "form_help",
    "status_check": "status_check",
    "grievance_file": "grievance_file",
    "task_plan": "task_plan",
    "yes_confirm": "yes",
    "no_cancel": "no",
}


class ConversationEngine:
    """The brain of the copilot — receives messages, detects intent, routes to services."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.llm = LLMRouter()
        self.scheme_advisor = SchemeAdvisor(db=db)
        self.wa = WhatsAppService()

    async def handle_message(
        self,
        phone_number: str,
        message_type: str,
        text_content: str,
        media_id: str | None = None,
        contact_name: str = "",
        interactive_id: str | None = None,
    ) -> None:
        """Main entry point for all incoming messages."""
        start_time = time.time()

        # 1. Look up or register employee
        employee = await get_employee_by_phone(phone_number, self.db)
        if not employee:
            employee = await self._auto_register(phone_number, contact_name)

        # 2. Get or create session (with timeout check)
        session = await self._get_or_create_session(employee.id)

        # 3. Log incoming message
        await self._log_message(
            session_id=session.id,
            direction="in",
            message_type=message_type,
            content_text=text_content or f"[{message_type}]",
            media_url=media_id,
        )

        # 4. Route based on message type
        if message_type == "audio" and media_id:
            response = await self._handle_voice(media_id, phone_number, employee, session)
        elif interactive_id:
            response = await self._handle_interactive(interactive_id, text_content, employee, session)
        else:
            response = await self._handle_text(text_content, employee, session)

        # 5. Send response via WhatsApp
        if isinstance(response, dict):
            # Structured response (interactive message)
            await self._send_structured(phone_number, response)
        else:
            # Plain text response
            await self.wa.send_text(phone_number, response)

        # 6. Log outgoing message
        elapsed_ms = int((time.time() - start_time) * 1000)
        response_text = response if isinstance(response, str) else response.get("text", str(response))
        await self._log_message(
            session_id=session.id,
            direction="out",
            message_type="text",
            content_text=response_text[:500],
            response_time_ms=elapsed_ms,
        )

        # 7. Store conversation context in Redis for multi-turn
        await self._update_session_context(
            session.id, employee.id, text_content, response_text
        )

    async def _handle_text(self, text: str, employee: Employee, session: ChatSession) -> str | dict:
        """Process a text message through the intent pipeline."""
        normalized = normalize_telugu_text(text)
        language = detect_language(normalized)
        intent = self._classify_intent(normalized)

        logger.info(
            "Intent classified",
            intent=intent,
            language=language,
            employee_id=employee.id,
        )

        # Check if this is a follow-up to a previous conversation
        context = await self._get_session_context(session.id, employee.id)
        if context and intent == "unclear":
            # Try to use conversation context to understand the follow-up
            intent = self._reclassify_with_context(normalized, context)

        return await self._route_intent(intent, normalized, language, employee, session, context)

    async def _handle_interactive(
        self, interactive_id: str, text: str, employee: Employee, session: ChatSession
    ) -> str | dict:
        """Handle interactive button/list replies."""
        language = detect_language(text) if text else "te"

        if interactive_id.startswith("scheme_"):
            # User selected a specific scheme from list
            scheme_code = interactive_id.replace("scheme_", "")
            result = await self.scheme_advisor.search(query=scheme_code, language=language)
            return result.answer

        elif interactive_id == "yes":
            # Confirmation — check what we were confirming
            context = await self._get_session_context(session.id, employee.id)
            if context and context.get("pending_action") == "form_generate":
                return await self._generate_pending_form(context, employee)
            return "✅ Confirmed!" if language == "en" else "✅ అలాగే!"

        elif interactive_id == "no":
            return "సరే, cancel చేశాను. ఏమైనా ఇతర సహాయం కావాలా?" if language == "te" else "OK, cancelled. Need anything else?"

        elif interactive_id == "show_scheme_list":
            return await self._build_scheme_list_message(employee, language)

        elif interactive_id == "form_help":
            return await self._handle_form_request("", language, employee)

        elif interactive_id == "status_check":
            return await self._handle_status_check("", language, employee)

        elif interactive_id == "grievance_file" or interactive_id.startswith("grv_"):
            return await self._handle_grievance(text or interactive_id, language, employee)

        elif interactive_id == "task_plan":
            return await self._handle_task_query("task plan", language, employee)

        # Default: treat the button text as a regular query
        return await self._handle_text(text, employee, session)

    async def _handle_voice(
        self, media_id: str, phone_number: str, employee: Employee, session: ChatSession
    ) -> str:
        """Handle voice message — download, transcribe, and process."""
        try:
            # Download voice note from WhatsApp CDN
            audio_data = await self.wa.download_media(media_id)

            # Transcribe using Whisper
            from app.services.voice_pipeline import VoicePipeline
            pipeline = VoicePipeline()
            result = await pipeline.transcribe(audio_data, language="te")

            if not result.text or result.text == "[Whisper not available]":
                return (
                    "🎤 Voice note అందింది కానీ transcribe చేయడంలో సమస్య.\n"
                    "దయచేసి text లో మీ ప్రశ్న పంపండి."
                )

            logger.info(
                "Voice transcribed",
                text_preview=result.text[:50],
                confidence=result.confidence,
                entities=result.entities,
            )

            # Send transcription confirmation
            await self.wa.send_text(
                phone_number,
                f"🎤 మీ voice note:\n\"{result.text[:200]}\"\n\nProcess చేస్తున్నాను..."
            )

            # Process the transcribed text as a regular message
            return await self._handle_text(result.text, employee, session)

        except Exception as e:
            logger.error("Voice processing failed", error=str(e))
            return (
                "🎤 Voice note process చేయడంలో సమస్య.\n"
                "దయచేసి text లో మీ ప్రశ్న పంపండి."
            )

    def _classify_intent(self, text: str) -> str:
        """Classify intent using keyword matching. Fast and works offline."""
        text_lower = text.lower()

        scores: dict[str, int] = {}
        for intent, keywords in INTENT_KEYWORDS.items():
            score = sum(1 for kw in keywords if kw.lower() in text_lower)
            if score > 0:
                scores[intent] = score

        if not scores:
            # Check if it references a known scheme
            if fuzzy_match_scheme(text):
                return "scheme_query"
            return "unclear"

        return max(scores, key=scores.get)

    def _reclassify_with_context(self, text: str, context: dict) -> str:
        """Re-classify an unclear intent using previous conversation context."""
        last_intent = context.get("last_intent", "")

        # Short affirmative responses are follow-ups
        affirmatives = {"అవును", "yes", "ok", "సరే", "చేయండి", "generate", "హా"}
        if text.lower().strip() in affirmatives:
            if last_intent in ("scheme_query", "form_help"):
                return last_intent
            return "yes_confirm"

        # Negatives
        negatives = {"వద్దు", "no", "cancel", "లేదు"}
        if text.lower().strip() in negatives:
            return "no_cancel"

        # Numbers might be Aadhaar digits for status check
        if text.strip().isdigit():
            if last_intent == "status_check":
                return "status_check"
            if last_intent == "eligibility_check":
                return "eligibility_check"

        # Default: keep as scheme_query if we were discussing schemes
        if last_intent == "scheme_query":
            return "scheme_query"

        return "unclear"

    async def _route_intent(
        self,
        intent: str,
        text: str,
        language: str,
        employee: Employee,
        session: ChatSession,
        context: dict | None = None,
    ) -> str | dict:
        """Route to the appropriate service based on detected intent."""

        if intent == "scheme_query":
            result = await self.scheme_advisor.search(query=text, language=language)
            return result.answer

        elif intent == "eligibility_check":
            return await self._handle_eligibility(text, language, employee, context)

        elif intent == "form_help":
            return await self._handle_form_request(text, language, employee)

        elif intent == "status_check":
            return await self._handle_status_check(text, language, employee)

        elif intent == "greeting":
            return self._build_greeting(employee, language)

        elif intent == "help":
            return self._build_help_menu(employee, language)

        elif intent == "thanks":
            return self._build_thanks(employee, language)

        elif intent == "grievance":
            return await self._handle_grievance(text, language, employee)

        elif intent == "task_query":
            return await self._handle_task_query(text, language, employee)

        elif intent == "language_switch":
            return await self._handle_language_switch(text, language, employee)

        elif intent == "yes_confirm":
            if context and context.get("pending_action"):
                return await self._generate_pending_form(context, employee)
            return "✅" if language == "en" else "✅ అలాగే!"

        elif intent == "no_cancel":
            return "Cancelled." if language == "en" else "Cancel చేశాను. ఏమైనా ఇతర సహాయం కావాలా?"

        else:
            return await self._handle_unclear(text, language, employee, context)

    # --- Response Builders ---

    def _build_greeting(self, employee: Employee, language: str) -> dict:
        """Build greeting with interactive menu buttons."""
        name = employee.name_te if employee.name_te != "Unknown" else employee.name_en or ""
        if language == "te":
            text = (
                f"నమస్కారం {name} గారు! 🙏\n\n"
                f"నేను AP సచివాలయం AI Copilot.\n"
                f"మీకు ఎలా సహాయం చేయగలను?"
            )
        else:
            text = (
                f"Namaskaram {name}! 🙏\n\n"
                f"I'm the AP Sachivalayam AI Copilot.\n"
                f"How can I help you?"
            )

        return {
            "type": "list",
            "text": text,
            "button_text": "సేవలు చూడండి",
            "sections": [
                {
                    "title": "AI Copilot Services",
                    "rows": [
                        {"id": "show_scheme_list", "title": "📋 పథకాలు / Schemes", "description": "Scheme info & eligibility"},
                        {"id": "form_help", "title": "📝 ఫారం / Form", "description": "Auto-fill forms & PDF"},
                        {"id": "status_check", "title": "🔍 స్థితి / Status", "description": "Track applications"},
                        {"id": "grievance_file", "title": "📋 ఫిర్యాదు / Grievance", "description": "File & track complaints"},
                        {"id": "task_plan", "title": "📊 Tasks / పనులు", "description": "Daily task plan"},
                    ],
                },
            ],
        }

    def _build_help_menu(self, employee: Employee, language: str) -> str:
        """Build help menu text."""
        if language == "te":
            return (
                "🤖 AP సచివాలయం AI Copilot — సహాయం\n\n"
                "నేను ఈ విధంగా సహాయం చేయగలను:\n\n"
                "📋 *పథకాల సమాచారం*\n"
                "   పథకం పేరు టైప్ చేయండి\n"
                "   ఉదా: \"అమ్మ ఒడి అర్హత?\"\n\n"
                "📝 *ఫారం నింపడం*\n"
                "   'ఫారం' అని టైప్ చేయండి\n"
                "   Voice note లో citizen details పంపండి\n\n"
                "🔍 *దరఖాస్తు స్థితి*\n"
                "   'స్థితి' అని టైప్ చేయండి\n\n"
                "🎤 *Voice notes*\n"
                "   Telugu లో voice note పంపండి — transcribe చేసి answer ఇస్తాను\n\n"
                "📋 *ఫిర్యాదు నమోదు*\n"
                "   'ఫిర్యాదు' అని టైప్ చేయండి\n"
                "   GRV number తో track చేయవచ్చు\n\n"
                "📊 *Daily Task Plan*\n"
                "   'task' అని టైప్ చేయండి\n"
                "   'task done' — task complete చేయడానికి\n\n"
                "💡 *Tips:*\n"
                "   • పథకం పేరు Telugu లో కానీ English లో కానీ టైప్ చేయవచ్చు\n"
                "   • Aadhaar number share చేయకండి — secure గా ఉంచుతాను"
            )
        return (
            "🤖 AP Sachivalayam AI Copilot — Help\n\n"
            "I can help you with:\n\n"
            "📋 *Scheme Information* — Type scheme name\n"
            "📝 *Form Filling* — Type 'form'\n"
            "🔍 *Application Status* — Type 'status'\n"
            "📋 *Grievance Filing* — Type 'grievance' or GRV number\n"
            "📊 *Daily Task Plan* — Type 'task'\n"
            "🎤 *Voice Notes* — Send voice in Telugu\n\n"
            "Example: \"Amma Vodi eligibility?\""
        )

    def _build_thanks(self, employee: Employee, language: str) -> str:
        """Acknowledge thanks."""
        name = employee.name_te if employee.name_te != "Unknown" else ""
        if language == "te":
            return f"🙏 ధన్యవాదాలు {name} గారు! ఏమైనా ఇతర సహాయం అవసరమైతే అడగండి."
        return "🙏 You're welcome! Ask if you need anything else."

    async def _handle_eligibility(
        self, text: str, language: str, employee: Employee, context: dict | None
    ) -> str:
        """Handle eligibility check requests."""
        # Try to identify scheme from text
        scheme_code = fuzzy_match_scheme(text)
        if not scheme_code and context:
            # Use scheme from context if available
            schemes = context.get("schemes_discussed", [])
            if schemes:
                scheme_code = schemes[-1]

        if not scheme_code:
            if language == "te":
                return (
                    "ఏ పథకానికి అర్హత check చేయాలి?\n"
                    "పథకం పేరు + citizen details చెప్పండి.\n\n"
                    "ఉదా: \"అమ్మ ఒడి, వయస్సు 35, income 2 లక్షలు, White card\""
                )
            return "Which scheme? Please provide scheme name + citizen details."

        # Extract citizen details from text and check eligibility
        result = await self.scheme_advisor.check_eligibility(
            scheme_code=scheme_code,
            citizen_details={"raw_text": text},
        )

        response = f"{'✅' if result.is_eligible else '❌'} {result.scheme_name_te}\n\n"
        response += result.reasoning_te

        if result.missing_documents:
            response += "\n\n📄 Missing documents:\n"
            for doc in result.missing_documents:
                response += f"  • {doc}\n"

        if result.next_steps_te:
            response += f"\n\n👉 Next: {result.next_steps_te}"

        return response

    async def _handle_form_request(self, text: str, language: str, employee: Employee) -> str | dict:
        """Handle form-related requests."""
        # Check if a specific scheme is mentioned
        scheme_code = fuzzy_match_scheme(text)

        if scheme_code:
            if language == "te":
                return (
                    f"📝 {scheme_code} ఫారం fill చేయడానికి:\n\n"
                    f"Citizen details voice note లో లేదా text లో పంపండి.\n"
                    f"ఈ details అవసరం:\n"
                    f"  • పేరు\n"
                    f"  • వయస్సు\n"
                    f"  • ఆదాయం\n"
                    f"  • Ration card type\n"
                    f"  • ఇతర relevant details\n\n"
                    f"నేను auto-fill చేసి PDF generate చేస్తాను."
                )
            return f"Send citizen details (name, age, income, ration card) for {scheme_code} form. I'll auto-fill and generate PDF."

        # No specific scheme — show options
        if language == "te":
            return {
                "type": "buttons",
                "text": (
                    "📝 ఏ పథకం కోసం ఫారం నింపాలి?\n\n"
                    "పథకం పేరు టైప్ చేయండి లేదా ఈ options నుండి select చేయండి:"
                ),
                "buttons": [
                    {"id": "scheme_YSR-AMMA-VODI", "title": "అమ్మ ఒడి"},
                    {"id": "scheme_YSR-PENSION-KANUKA", "title": "పెన్షన్"},
                    {"id": "scheme_YSR-RYTHU-BHAROSA", "title": "రైతు భరోసా"},
                ],
            }
        return "Which scheme form? Type the scheme name or select from common options."

    async def _handle_status_check(self, text: str, language: str, employee: Employee) -> str:
        """Handle application status check requests."""
        # Check if an application ID or Aadhaar digits are provided
        import re
        numbers = re.findall(r"\d{4,}", text)

        if numbers:
            # Try GSWS status check
            try:
                from app.services.gsws_bridge import GSWSBridge
                bridge = GSWSBridge(db=self.db)
                status = await bridge.check_application_status(numbers[0])
                return f"📋 Application Status:\n{status}"
            except Exception:
                if language == "te":
                    return (
                        f"🔍 Application ID: {numbers[0]}\n\n"
                        "GSWS portal ప్రస్తుతం అందుబాటులో లేదు.\n"
                        "దయచేసి కొద్దిసేపట్లో మళ్ళీ ప్రయత్నించండి."
                    )
                return f"GSWS portal is currently unavailable. Please try again later."

        # No ID provided — ask for it
        if language == "te":
            return (
                "🔍 దరఖాస్తు status check చేయడానికి:\n\n"
                "ఈ వాటిలో ఏదైనా ఒకటి పంపండి:\n"
                "  • Application ID\n"
                "  • GSWS reference number\n"
                "  • Citizen Aadhaar last 4 digits"
            )
        return "Please share: Application ID, GSWS reference number, or citizen's last 4 Aadhaar digits."

    async def _handle_unclear(
        self, text: str, language: str, employee: Employee, context: dict | None
    ) -> str:
        """Handle unclear intent — use Claude with conversation history."""
        try:
            # Build conversation history for context
            history_prompt = ""
            if context and context.get("history"):
                history_prompt = "Previous conversation:\n"
                for msg in context["history"][-6:]:  # Last 3 turns
                    role = "Employee" if msg["direction"] == "in" else "Copilot"
                    history_prompt += f"{role}: {msg['text']}\n"
                history_prompt += "\n"

            prompt = f"{history_prompt}Employee's new message: {text}"

            response = await self.llm.route(
                task_type="complex_query",
                prompt=prompt,
            )
            return response

        except Exception as e:
            logger.error("LLM fallback error", error=str(e))
            if language == "te":
                return {
                    "type": "buttons",
                    "text": (
                        "క్షమించండి, మీ ప్రశ్న అర్థం కాలేదు.\n"
                        "ఈ options లో ఏదైనా select చేయండి:"
                    ),
                    "buttons": [
                        {"id": "show_scheme_list", "title": "📋 పథకాలు"},
                        {"id": "grievance_file", "title": "📋 ఫిర్యాదు"},
                        {"id": "task_plan", "title": "📊 Tasks"},
                    ],
                }
            return "Sorry, I didn't understand. Please try: scheme name, 'form', or 'status'."

    async def _handle_grievance(self, text: str, language: str, employee: Employee) -> str | dict:
        """Handle grievance filing and tracking requests."""
        import re

        # Check if tracking an existing grievance
        grv_match = re.search(r"GRV-\d{4}-\d{4}", text, re.IGNORECASE)
        if grv_match:
            try:
                from app.services.grievance_service import GrievanceService
                service = GrievanceService(db=self.db)
                result = await service.get_by_reference(grv_match.group().upper())
                if result:
                    status_icons = {
                        "open": "🟡", "acknowledged": "🔵", "in_progress": "🔄",
                        "escalated": "🟠", "resolved": "✅", "closed": "⬛",
                    }
                    icon = status_icons.get(result.status, "❓")
                    response = (
                        f"📋 ఫిర్యాదు: {result.reference_number}\n\n"
                        f"{icon} Status: {result.status}\n"
                        f"📁 Category: {result.category}\n"
                        f"🏢 Department: {result.department}\n"
                        f"⚡ Priority: {result.priority}\n"
                    )
                    if result.resolution_notes_te:
                        response += f"\n✅ Resolution: {result.resolution_notes_te}"
                    if result.is_sla_breached:
                        response += "\n\n⚠️ SLA breached — escalated to higher authority"
                    return response
            except Exception as e:
                logger.error("Grievance lookup failed", error=str(e))

        # New grievance filing flow
        if language == "te":
            return {
                "type": "buttons",
                "text": (
                    "📋 ఫిర్యాదు నమోదు\n\n"
                    "పౌరుని సమస్య వివరాలు పంపండి:\n"
                    "• పౌరుని పేరు\n"
                    "• సమస్య వివరణ\n"
                    "• ఏ విభాగం (Agriculture, Health, Education...)\n\n"
                    "లేదా category select చేయండి:"
                ),
                "buttons": [
                    {"id": "grv_welfare", "title": "🏠 సంక్షేమం"},
                    {"id": "grv_health", "title": "🏥 ఆరోగ్యం"},
                    {"id": "grv_agriculture", "title": "🌾 వ్యవసాయం"},
                ],
            }
        return (
            "To file a grievance, send:\n"
            "• Citizen name\n"
            "• Problem description\n"
            "• Department (Agriculture, Health, Education, etc.)\n\n"
            "Or type a GRV reference number to track existing grievance."
        )

    async def _handle_task_query(self, text: str, language: str, employee: Employee) -> str:
        """Handle task-related queries — show daily plan or task status."""
        try:
            from app.services.task_service import TaskService
            service = TaskService(db=self.db)

            # Check if completing a task
            complete_keywords = ["done", "complete", "అయింది", "పూర్తి", "finished"]
            if any(kw in text.lower() for kw in complete_keywords):
                # Get in-progress tasks
                tasks, _ = await service.list_tasks(
                    employee_id=employee.id, status="in_progress"
                )
                if tasks:
                    from app.schemas.task import TaskUpdateRequest
                    await service.update_task(
                        tasks[0].id,
                        TaskUpdateRequest(status="completed"),
                        employee.id,
                    )
                    return (
                        f"✅ Task complete: {tasks[0].title_te}\n\n"
                        f"బాగుంది! తదుపరి task కోసం 'task' అని టైప్ చేయండి."
                        if language == "te"
                        else f"Task completed: {tasks[0].title_te}\nType 'task' for next task."
                    )

            # Generate/show daily plan
            plan = await service.generate_daily_plan(employee.id)

            if not plan.tasks:
                return (
                    "🎉 ఈ రోజు pending tasks లేవు! మీరు అన్ని tasks పూర్తి చేశారు."
                    if language == "te"
                    else "No pending tasks for today! You're all caught up."
                )

            # Format plan as message
            lines = ["📋 ఈ రోజు Task Plan:\n" if language == "te" else "Today's Task Plan:\n"]

            if plan.ai_summary_te and language == "te":
                lines.append(f"💡 {plan.ai_summary_te}\n")

            for task in plan.tasks[:8]:
                status_icon = {"pending": "⬜", "in_progress": "🔄", "overdue": "🔴"}.get(task.status, "⬜")
                priority_icon = {"urgent": "🔴", "high": "🟠", "medium": "🟡", "low": "🟢"}.get(task.priority, "⬜")

                lines.append(
                    f"{task.rank}. {status_icon} {task.title_te}\n"
                    f"   {priority_icon} {task.department} • ~{task.estimated_minutes} min"
                )
                if task.reason_te:
                    lines.append(f"   💡 {task.reason_te}")

            lines.append(f"\n⏱️ Total: ~{plan.total_estimated_minutes} min")
            lines.append("\n'task done' — task complete చేయడానికి" if language == "te" else "\n'task done' — to mark current task complete")

            return "\n".join(lines)

        except Exception as e:
            logger.error("Task query failed", error=str(e))
            return (
                "Task plan load చేయడంలో సమస్య. దయచేసి మళ్ళీ ప్రయత్నించండి."
                if language == "te"
                else "Error loading task plan. Please try again."
            )

    async def _handle_language_switch(self, text: str, language: str, employee: Employee) -> str:
        """Handle language preference change."""
        english_triggers = {"english", "ఇంగ్లీష్", "english lo", "english please"}
        telugu_triggers = {"telugu", "తెలుగు", "telugu lo", "telugu please"}

        target = "en"  # default to English if unclear
        text_lower = text.lower()
        for trigger in telugu_triggers:
            if trigger in text_lower:
                target = "te"
                break
        for trigger in english_triggers:
            if trigger in text_lower:
                target = "en"
                break

        employee.preferred_language = target
        await self.db.flush()

        if target == "en":
            return (
                "✅ Language changed to English.\n"
                "I'll respond in English from now on.\n\n"
                "How can I help you?"
            )
        return (
            "✅ భాష తెలుగుకు మార్చబడింది.\n"
            "ఇకనుండి తెలుగులో సమాధానం ఇస్తాను.\n\n"
            "మీకు ఎలా సహాయం చేయగలను?"
        )

    async def _build_scheme_list_message(self, employee: Employee, language: str) -> dict:
        """Build interactive list of top schemes."""
        return {
            "type": "list",
            "text": "📋 ముఖ్యమైన పథకాలు — ఒకటి select చేయండి:" if language == "te"
                    else "📋 Major Schemes — Select one:",
            "button_text": "పథకాలు చూడండి",
            "sections": [
                {
                    "title": "🌾 Agriculture",
                    "rows": [
                        {"id": "scheme_YSR-RYTHU-BHAROSA", "title": "రైతు భరోసా", "description": "₹13,500/year for farmers"},
                        {"id": "scheme_YSR-YANTRA-SEVA", "title": "యంత్ర సేవ", "description": "Subsidized farm machinery"},
                    ],
                },
                {
                    "title": "📚 Education",
                    "rows": [
                        {"id": "scheme_YSR-AMMA-VODI", "title": "అమ్మ ఒడి", "description": "₹15,000 for school children"},
                        {"id": "scheme_JAGANANNA-VIDYA-DEEVENA", "title": "విద్యా దీవెన", "description": "Full tuition fee reimbursement"},
                    ],
                },
                {
                    "title": "🏥 Health & Welfare",
                    "rows": [
                        {"id": "scheme_YSR-AAROGYASRI", "title": "ఆరోగ్యశ్రీ", "description": "₹25L free medical treatment"},
                        {"id": "scheme_YSR-PENSION-KANUKA", "title": "పెన్షన్ కానుక", "description": "₹3,000/month pension"},
                        {"id": "scheme_YSR-CHEYUTHA", "title": "చేయూత", "description": "₹18,750 for women (45-60)"},
                    ],
                },
                {
                    "title": "🏠 Housing & Others",
                    "rows": [
                        {"id": "scheme_PEDALANDARIKI-ILLU", "title": "పేదలందరికీ ఇళ్ళు", "description": "Free houses for poor"},
                        {"id": "scheme_YSR-KALYANAMASTHU", "title": "కళ్యాణమస్తు", "description": "₹1L marriage assistance"},
                    ],
                },
            ],
        }

    async def _generate_pending_form(self, context: dict, employee: Employee) -> str:
        """Generate a PDF form that was pending confirmation."""
        submission_id = context.get("pending_submission_id")
        if not submission_id:
            return "❌ Pending form not found. దయచేసి మళ్ళీ details పంపండి."

        try:
            from app.services.pdf_generator import PDFGenerator
            from uuid import UUID

            generator = PDFGenerator(db=self.db)
            pdf_path = await generator.generate(UUID(submission_id))

            if pdf_path:
                # Send PDF via WhatsApp (async to not block response)
                from app.workers.form_generation import generate_and_send_pdf
                generate_and_send_pdf.delay(submission_id, employee.phone_number)

                return (
                    "✅ PDF generate అవుతోంది!\n"
                    "కొద్దిసేపట్లో WhatsApp లో PDF document వస్తుంది.\n\n"
                    "GSWS portal కి submit చేయాలంటే 'submit' అని reply చేయండి."
                )
            else:
                return "❌ PDF generation failed. దయచేసి మళ్ళీ ప్రయత్నించండి."

        except Exception as e:
            logger.error("Form generation failed", error=str(e))
            return "❌ Form generation లో సమస్య. దయచేసి మళ్ళీ ప్రయత్నించండి."

    # --- Session & Context Management ---

    async def _send_structured(self, phone: str, response: dict) -> None:
        """Send a structured response (buttons or list) via WhatsApp."""
        msg_type = response.get("type", "text")

        if msg_type == "buttons":
            await self.wa.send_buttons(
                to=phone,
                body=response["text"],
                buttons=response["buttons"],
            )
        elif msg_type == "list":
            await self.wa.send_list(
                to=phone,
                body=response["text"],
                button_text=response.get("button_text", "Options"),
                sections=response["sections"],
            )
        else:
            await self.wa.send_text(phone, response.get("text", str(response)))

    async def _get_or_create_session(self, employee_id: int) -> ChatSession:
        """Get active session or create a new one (with timeout)."""
        cutoff = datetime.now(timezone.utc) - SESSION_TIMEOUT

        result = await self.db.execute(
            select(ChatSession)
            .where(ChatSession.employee_id == employee_id)
            .where(ChatSession.ended_at.is_(None))
            .where(ChatSession.started_at > cutoff)
            .order_by(ChatSession.started_at.desc())
            .limit(1)
        )
        session = result.scalar_one_or_none()

        if not session:
            session = ChatSession(employee_id=employee_id)
            self.db.add(session)
            await self.db.flush()

        return session

    async def _auto_register(self, phone_number: str, contact_name: str) -> Employee:
        """Auto-register a new employee from their first WhatsApp message."""
        employee = Employee(
            phone_number=phone_number,
            name_te=contact_name or "Unknown",
            name_en=contact_name or "Unknown",
            designation="Unknown",
            department="Unknown",
        )
        self.db.add(employee)
        await self.db.flush()
        logger.info("Auto-registered employee", phone=phone_number[-4:])
        return employee

    async def _log_message(
        self,
        session_id: uuid.UUID,
        direction: str,
        message_type: str,
        content_text: str | None = None,
        media_url: str | None = None,
        response_time_ms: int | None = None,
    ) -> None:
        """Log a message to the database for audit trail."""
        msg = Message(
            session_id=session_id,
            direction=direction,
            message_type=message_type,
            content_text=content_text,
            content_media_url=media_url,
            response_time_ms=response_time_ms,
        )
        self.db.add(msg)
        await self.db.flush()

    async def _update_session_context(
        self, session_id: uuid.UUID, employee_id: int, user_text: str, bot_text: str
    ) -> None:
        """Store conversation context in Redis for multi-turn support."""
        import json

        try:
            key = f"conv:{employee_id}"
            existing = await redis_client.get(key)

            if existing:
                context = json.loads(existing)
            else:
                context = {"history": [], "last_intent": "", "schemes_discussed": []}

            # Add to history (keep last N messages)
            context["history"].append({"direction": "in", "text": user_text[:300]})
            context["history"].append({"direction": "out", "text": bot_text[:300]})
            context["history"] = context["history"][-MAX_HISTORY_MESSAGES * 2:]

            # Track intent and schemes
            intent = self._classify_intent(user_text)
            context["last_intent"] = intent

            scheme = fuzzy_match_scheme(user_text)
            if scheme:
                if scheme not in context["schemes_discussed"]:
                    context["schemes_discussed"].append(scheme)
                context["schemes_discussed"] = context["schemes_discussed"][-5:]

            await redis_client.setex(key, int(SESSION_TIMEOUT.total_seconds()), json.dumps(context, ensure_ascii=False))

        except Exception as e:
            logger.debug("Session context update failed", error=str(e))

    async def _get_session_context(self, session_id: uuid.UUID, employee_id: int) -> dict | None:
        """Retrieve conversation context from Redis."""
        import json

        try:
            key = f"conv:{employee_id}"
            data = await redis_client.get(key)
            if data:
                return json.loads(data)
        except Exception:
            pass
        return None
