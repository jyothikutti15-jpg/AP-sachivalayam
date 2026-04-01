import pytest


@pytest.fixture
def sample_whatsapp_text_payload():
    return {
        "object": "whatsapp_business_account",
        "entry": [{
            "id": "123456789",
            "changes": [{
                "field": "messages",
                "value": {
                    "messaging_product": "whatsapp",
                    "metadata": {"display_phone_number": "919876543210", "phone_number_id": "123"},
                    "contacts": [{"profile": {"name": "Test Employee"}, "wa_id": "919876543210"}],
                    "messages": [{
                        "from": "919876543210",
                        "id": "msg_001",
                        "timestamp": "1234567890",
                        "type": "text",
                        "text": {"body": "అమ్మ ఒడి అర్హత ఏమిటి?"}
                    }]
                }
            }]
        }]
    }


@pytest.fixture
def sample_voice_payload():
    return {
        "object": "whatsapp_business_account",
        "entry": [{
            "id": "123456789",
            "changes": [{
                "field": "messages",
                "value": {
                    "messaging_product": "whatsapp",
                    "contacts": [{"profile": {"name": "Test Employee"}, "wa_id": "919876543210"}],
                    "messages": [{
                        "from": "919876543210",
                        "id": "msg_002",
                        "timestamp": "1234567890",
                        "type": "audio",
                        "audio": {"id": "audio_123", "mime_type": "audio/ogg"}
                    }]
                }
            }]
        }]
    }
