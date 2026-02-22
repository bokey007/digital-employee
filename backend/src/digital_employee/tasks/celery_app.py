"""Celery application configuration."""

from __future__ import annotations

from celery import Celery
from celery.schedules import crontab

from digital_employee.settings import get_settings

settings = get_settings()

celery_app = Celery(
    "digital_employee",
    broker=settings.redis_url,
    backend=settings.redis_url,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    # Auto-discover tasks in the tasks module
    imports=["digital_employee.tasks.email_tasks", "digital_employee.tasks.workflow_tasks"],
)

# Periodic beat schedule
celery_app.conf.beat_schedule = {
    "poll-inbox-every-60s": {
        "task": "digital_employee.tasks.email_tasks.poll_inbox",
        "schedule": 60.0,  # Every minute
    },
    "check-reminders-daily": {
        "task": "digital_employee.tasks.email_tasks.check_and_send_reminders",
        "schedule": crontab(hour=9, minute=0),  # Daily at 9 AM UTC
    },
}
