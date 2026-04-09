from fastapi import APIRouter

from app.api.v1 import audit, checklist, circulars, citizens, dashboard, forms, grievances, health, outreach, performance, reminders, schemes, supervisor, tasks, training, voice, whatsapp

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
api_v1_router.include_router(citizens.router, prefix="/citizens", tags=["Citizens"])
api_v1_router.include_router(supervisor.router, prefix="/supervisor", tags=["Supervisor"])
api_v1_router.include_router(training.router, prefix="/training", tags=["Training"])
api_v1_router.include_router(outreach.router, tags=["Outreach"])
api_v1_router.include_router(checklist.router, prefix="/checklist", tags=["Document Checklist"])
api_v1_router.include_router(circulars.router, prefix="/circulars", tags=["GO/Circulars"])
api_v1_router.include_router(reminders.router, prefix="/reminders", tags=["Citizen Reminders"])
