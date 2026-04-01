from fastapi import APIRouter

from app.api.v1 import audit, dashboard, forms, grievances, health, performance, schemes, tasks, voice, whatsapp

api_v1_router = APIRouter()

api_v1_router.include_router(health.router, tags=["Health"])
api_v1_router.include_router(whatsapp.router, prefix="/whatsapp", tags=["WhatsApp"])
api_v1_router.include_router(schemes.router, prefix="/schemes", tags=["Schemes"])
api_v1_router.include_router(forms.router, prefix="/forms", tags=["Forms"])
api_v1_router.include_router(voice.router, prefix="/voice", tags=["Voice"])
api_v1_router.include_router(dashboard.router, prefix="/analytics", tags=["Analytics"])
api_v1_router.include_router(grievances.router, prefix="/grievances", tags=["Grievances"])
api_v1_router.include_router(tasks.router, prefix="/tasks", tags=["Tasks"])
api_v1_router.include_router(audit.router, prefix="/audit", tags=["Audit"])
api_v1_router.include_router(performance.router, prefix="/performance", tags=["Performance"])
