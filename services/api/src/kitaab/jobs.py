"""Background jobs. Celery tasks (workers/tasks.py) and the inline test queue
both call these functions, so behaviour is the same in tests and production."""

import logging
import uuid
from collections.abc import Callable
from typing import Any

import httpx2

from kitaab.container import Services
from kitaab.domain import notifications, payments, purge, quotes, shipping, uploads
from kitaab.domain.context import Ctx

log = logging.getLogger(__name__)


def _with_ctx(services: Services, work: Callable[[Ctx], Any]) -> Any:
    with services.session() as session:
        result = work(Ctx(session, services))
        session.commit()
        return result


def validate_upload(services: Services, upload_id: str) -> None:
    uploads.run_validation(services, upload_id)


def validation_failed(services: Services, upload_id: str) -> None:
    uploads.mark_check_failed(services, upload_id)


def deliver_notification(services: Services, notification_id: str, send_sms: bool = False) -> None:
    notifications.deliver(services, notification_id, send_sms)


def process_refund(services: Services, refund_id: str) -> None:
    _with_ctx(services, lambda ctx: payments.process_refund(ctx, uuid.UUID(refund_id)))


def expire_quotes(services: Services) -> int:
    count: int = _with_ctx(services, quotes.expire_due)
    return count


def expire_pending_payments(services: Services) -> int:
    count: int = _with_ctx(services, payments.expire_pending_payments)
    return count


def poll_courier_status(services: Services) -> int:
    count: int = _with_ctx(services, shipping.poll_couriers)
    return count


def purge_files(services: Services, dry_run: bool | None = None) -> dict[str, Any]:
    report = _with_ctx(services, lambda ctx: purge.run_purge(ctx, dry_run=dry_run))
    return {k: v for k, v in vars(report).items() if k != "upload_ids"}


def deliver_webhook(services: Services, path: str, body: str, headers: dict[str, str]) -> None:
    """Mock providers post their webhooks back to the API, like real ones would."""
    post = services.extras.get("http_post")
    if post is not None:
        post(path, body.encode(), headers)
        return
    url = services.settings.internal_api_url.rstrip("/") + path
    response = httpx2.post(
        url,
        content=body.encode(),
        headers={**headers, "Content-Type": "application/json"},
        timeout=10,
    )
    if response.status_code >= 400:
        log.warning(
            "mock webhook delivery failed", extra={"status": response.status_code, "path": path}
        )


JOBS: dict[str, Callable[..., Any]] = {
    "validate_upload": validate_upload,
    "validation_failed": validation_failed,
    "deliver_notification": deliver_notification,
    "process_refund": process_refund,
    "expire_quotes": expire_quotes,
    "expire_pending_payments": expire_pending_payments,
    "poll_courier_status": poll_courier_status,
    "purge_files": purge_files,
    "deliver_webhook": deliver_webhook,
}
