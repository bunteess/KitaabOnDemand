"""Celery application: background jobs and the beat schedule."""

from celery import Celery

from kitaab.config import get_settings

settings = get_settings()

app = Celery("kitaab", broker=settings.redis_url, backend=None)
app.conf.update(
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
    task_default_queue="default",
    timezone="UTC",
    enable_utc=True,
    broker_connection_retry_on_startup=True,
)


@app.task(name="kitaab.ping")
def ping() -> str:
    return "pong"
