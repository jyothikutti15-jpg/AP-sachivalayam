"""Tests for WhatsApp webhook handling."""
import json

from app.schemas.whatsapp import WhatsAppWebhookPayload


class TestWebhookParsing:
    """Test WhatsApp webhook payload parsing."""

    def test_parse_text_message(self, sample_whatsapp_text_payload):
        payload = WhatsAppWebhookPayload.model_validate(sample_whatsapp_text_payload)
        assert payload.object == "whatsapp_business_account"
        assert len(payload.entry) == 1
        assert payload.entry[0].changes[0].field == "messages"

        messages = payload.entry[0].changes[0].value.get("messages", [])
        assert len(messages) == 1
        assert messages[0]["type"] == "text"
        assert "అమ్మ ఒడి" in messages[0]["text"]["body"]

    def test_parse_voice_message(self, sample_voice_payload):
        payload = WhatsAppWebhookPayload.model_validate(sample_voice_payload)
        messages = payload.entry[0].changes[0].value.get("messages", [])
        assert messages[0]["type"] == "audio"
        assert messages[0]["audio"]["id"] == "audio_123"

    def test_extract_phone_number(self, sample_whatsapp_text_payload):
        payload = WhatsAppWebhookPayload.model_validate(sample_whatsapp_text_payload)
        messages = payload.entry[0].changes[0].value.get("messages", [])
        phone = messages[0]["from"]
        assert phone == "919876543210"

    def test_extract_contact_name(self, sample_whatsapp_text_payload):
        payload = WhatsAppWebhookPayload.model_validate(sample_whatsapp_text_payload)
        contacts = payload.entry[0].changes[0].value.get("contacts", [])
        name = contacts[0]["profile"]["name"]
        assert name == "Test Employee"


class TestIntentClassification:
    """Test the conversation engine's intent classification."""

    def test_scheme_query_intent(self):
        from app.services.conversation_engine import ConversationEngine

        engine = ConversationEngine.__new__(ConversationEngine)
        assert engine._classify_intent("అమ్మ ఒడి అర్హత ఏమిటి?") == "scheme_query"
        assert engine._classify_intent("rythu bharosa eligibility") == "scheme_query"
        assert engine._classify_intent("pension scheme details") == "scheme_query"

    def test_form_help_intent(self):
        from app.services.conversation_engine import ConversationEngine

        engine = ConversationEngine.__new__(ConversationEngine)
        assert engine._classify_intent("ఫారం నింపాలి") == "form_help"
        assert engine._classify_intent("fill application form") == "form_help"

    def test_status_check_intent(self):
        from app.services.conversation_engine import ConversationEngine

        engine = ConversationEngine.__new__(ConversationEngine)
        assert engine._classify_intent("status check pending") == "status_check"
        assert engine._classify_intent("దరఖాస్తు స్థితి") == "status_check"

    def test_greeting_intent(self):
        from app.services.conversation_engine import ConversationEngine

        engine = ConversationEngine.__new__(ConversationEngine)
        assert engine._classify_intent("నమస్కారం") == "greeting"
        assert engine._classify_intent("hello") == "greeting"
        assert engine._classify_intent("hi") == "greeting"

    def test_unclear_intent(self):
        from app.services.conversation_engine import ConversationEngine

        engine = ConversationEngine.__new__(ConversationEngine)
        result = engine._classify_intent("qwerty gibberish zxcvbn")
        assert result == "unclear"
