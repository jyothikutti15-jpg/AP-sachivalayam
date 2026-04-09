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
    task_acks_late=True,          # task is not acked until it completes/fails
    worker_prefetch_multiplier=1,
    task_max_retries=3,           # global safety-net ceiling for all tasks
)

# ---------------------------------------------------------------------------
# Exponential backoff reference values (used in autoretry_for decorators)
# ---------------------------------------------------------------------------
# User-facing tasks (transcribe, form PDF, notifications):
#   retry_backoff=30, retry_backoff_max=300  →  ~30s, 60s, 120s
# Background / periodic tasks:
#   retry_backoff=60, retry_backoff_max=3600 →  ~60s, 120s, 240s
# retry_jitter=True adds ±25% randomisation to avoid thundering herd.

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
    "scan-outreach-weekly": {
        "task": "scan_outreach",
        "schedule": crontab(day_of_week=0, hour=3, minute=0),  # Sunday 3 AM IST
    },
    "send-citizen-reminders": {
        "task": "send_due_reminders",
        "schedule": crontab(hour=8, minute=30),  # 8:30 AM IST daily
    },
}

# Auto-discover tasks
celery_app.autodiscover_tasks([
    "app.workers.voice_transcription",
    "app.workers.form_generation",
    "app.workers.knowledge_sync",
    "app.workers.grievance_escalation",
    "app.workers.task_scheduler",
    "app.workers.outreach_scanner",
    "app.workers.reminder_sender",
])
