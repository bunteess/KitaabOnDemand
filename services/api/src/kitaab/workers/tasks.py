"""Celery tasks: thin wrappers around kitaab.jobs."""

from functools import lru_cache
from typing import Any

from celery import Task
from celery.signals import worker_process_init

from kitaab import jobs
from kitaab.config import get_settings
from kitaab.container import Services, build_services
from kitaab.logging import configure_logging
from kitaab.workers.celery_app import app


@lru_cache
def services() -> Services:
    return build_services(get_settings())


@worker_process_init.connect
def _init(**_: Any) -> None:
    configure_logging(get_settings().log_level)


VALIDATION_ATTEMPTS = 5


@app.task(name="validate_upload", bind=True, max_retries=VALIDATION_ATTEMPTS)
def validate_upload(self: "Task[Any, Any]", upload_id: str) -> None:
    """Retries with backoff; if every attempt fails the upload is rejected as
    "could not be checked" rather than left waiting forever."""
    try:
        jobs.validate_upload(services(), upload_id)
    except Exception as error:
        if self.request.retries >= VALIDATION_ATTEMPTS:
            jobs.validation_failed(services(), upload_id)
            raise
        raise self.retry(exc=error, countdown=15 * 2**self.request.retries) from error


@app.task(name="deliver_notification", autoretry_for=(OSError,), retry_backoff=True, max_retries=5)
def deliver_notification(notification_id: str, send_sms: bool = False) -> None:
    jobs.deliver_notification(services(), notification_id, send_sms)


@app.task(name="process_refund")
def process_refund(refund_id: str) -> None:
    jobs.process_refund(services(), refund_id)


@app.task(name="expire_quotes")
def expire_quotes() -> int:
    return jobs.expire_quotes(services())


@app.task(name="expire_pending_payments")
def expire_pending_payments() -> int:
    return jobs.expire_pending_payments(services())


@app.task(name="poll_courier_status")
def poll_courier_status() -> int:
    return jobs.poll_courier_status(services())


@app.task(name="purge_files")
def purge_files() -> dict[str, Any]:
    return jobs.purge_files(services())


@app.task(name="deliver_webhook", autoretry_for=(OSError,), retry_backoff=True, max_retries=8)
def deliver_webhook(path: str, body: str, headers: dict[str, str]) -> None:
    jobs.deliver_webhook(services(), path, body, headers)
