"""Celery application: background jobs and the beat schedule."""

from celery import Celery
from celery.schedules import crontab

from kitaab.config import get_settings

settings = get_settings()

app = Celery("kitaab", broker=settings.redis_url, backend=None, include=["kitaab.workers.tasks"])
app.conf.update(
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
    task_default_queue="default",
    timezone="UTC",
    enable_utc=True,
    broker_connection_retry_on_startup=True,
    worker_hijack_root_logger=False,
    beat_schedule={
        "expire-quotes": {"task": "expire_quotes", "schedule": crontab(minute="*/5")},
        "expire-pending-payments": {
            "task": "expire_pending_payments",
            "schedule": crontab(minute="*/15"),
        },
        "poll-courier-status": {"task": "poll_courier_status", "schedule": crontab(minute="*/30")},
        "purge-files": {"task": "purge_files", "schedule": crontab(minute=7)},
    },
)


@app.task(name="kitaab.ping")
def ping() -> str:
    return "pong"
