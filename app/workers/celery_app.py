from celery import Celery
from celery.schedules import crontab

from app.config import get_settings

settings = get_settings()

celery_app = Celery(
    "sachivalayam",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Kolkata",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
)

# Periodic tasks
celery_app.conf.beat_schedule = {
    "process-offline-queue": {
        "task": "app.workers.voice_transcription.process_offline_queue",
        "schedule": 300.0,  # Every 5 minutes
    },
    "nightly-gsws-sync": {
        "task": "app.workers.knowledge_sync.sync_gsws_data",
        "schedule": crontab(hour=2, minute=0),  # 2 AM IST
    },
    "daily-metrics-aggregation": {
        "task": "app.workers.knowledge_sync.aggregate_daily_metrics",
        "schedule": crontab(hour=23, minute=30),  # 11:30 PM IST
    },
    "check-grievance-sla": {
        "task": "check_grievance_sla",
        "schedule": 1800.0,  # Every 30 minutes
    },
    "create-recurring-tasks": {
        "task": "create_recurring_tasks",
        "schedule": crontab(hour=5, minute=30),  # 5:30 AM IST
    },
    "generate-daily-plans": {
        "task": "generate_daily_plans",
        "schedule": crontab(hour=6, minute=0),  # 6 AM IST
    },
}

# Auto-discover tasks
celery_app.autodiscover_tasks([
    "app.workers.voice_transcription",
    "app.workers.form_generation",
    "app.workers.knowledge_sync",
    "app.workers.grievance_escalation",
    "app.workers.task_scheduler",
])
