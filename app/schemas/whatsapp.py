from pydantic import BaseModel


class WebhookChange(BaseModel):
    field: str
    value: dict


class WebhookEntry(BaseModel):
    id: str
    changes: list[WebhookChange]


class WhatsAppWebhookPayload(BaseModel):
    object: str = "whatsapp_business_account"
    entry: list[WebhookEntry]


class WhatsAppTextMessage(BaseModel):
    to: str
    type: str = "text"
    text: dict  # {"body": "..."}


class WhatsAppInteractiveButton(BaseModel):
    type: str = "button"
    id: str
    title: str


class WhatsAppInteractiveMessage(BaseModel):
    to: str
    type: str = "interactive"
    interactive: dict
