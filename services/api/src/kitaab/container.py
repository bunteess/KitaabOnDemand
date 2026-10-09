"""Everything a request handler or background job needs, built once per process.

The API puts a `Services` on `app.state`; Celery workers build their own. Tests
build one with fakes (in-memory providers, a frozen clock, an inline task queue).
"""

import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Protocol

import redis
from sqlalchemy.orm import Session, sessionmaker

from kitaab import clock as clock_module
from kitaab.clock import Clock, OffsetClock, SystemClock
from kitaab.config import Settings
from kitaab.db import get_session_factory
from kitaab.providers.antivirus import ClamdScanner, VirusScanner
from kitaab.providers.courier import CourierRegistry, build_couriers
from kitaab.providers.id_tokens import FakeIdTokenVerifier, GoogleIdTokenVerifier, IdTokenVerifier
from kitaab.providers.payment import PaymentRegistry, build_payments
from kitaab.providers.push import PushProvider, build_push
from kitaab.providers.sms import SmsProvider, build_sms
from kitaab.providers.storage import ObjectStore, S3ObjectStore
from kitaab.security.ratelimit import RateLimiter

log = logging.getLogger(__name__)


class TaskQueue(Protocol):
    def enqueue(self, name: str, **kwargs: Any) -> None: ...


class CeleryTaskQueue:
    def enqueue(self, name: str, **kwargs: Any) -> None:
        from kitaab.workers.celery_app import app

        app.send_task(name, kwargs=kwargs)


@dataclass
class InlineTaskQueue:
    """Runs jobs in-process. With `eager=False` they wait until `run_pending()`."""

    services: "Services | None" = None
    eager: bool = True
    pending: list[tuple[str, dict[str, Any]]] = field(default_factory=list)

    def enqueue(self, name: str, **kwargs: Any) -> None:
        if self.eager:
            self._run(name, kwargs)
        else:
            self.pending.append((name, kwargs))

    def run_pending(self) -> int:
        count = 0
        while self.pending:
            name, kwargs = self.pending.pop(0)
            self._run(name, kwargs)
            count += 1
        return count

    def _run(self, name: str, kwargs: dict[str, Any]) -> None:
        from kitaab.jobs import JOBS

        if self.services is None:
            raise RuntimeError("InlineTaskQueue needs services")
        JOBS[name](self.services, **kwargs)


@dataclass
class Services:
    settings: Settings
    clock: Clock
    session_factory: sessionmaker[Session]
    redis: "redis.Redis"
    store: ObjectStore
    sms: SmsProvider
    payments: PaymentRegistry
    couriers: CourierRegistry
    push: PushProvider
    scanner: VirusScanner | None
    id_tokens: IdTokenVerifier
    rate_limiter: RateLimiter
    tasks: TaskQueue
    extras: dict[str, Callable[..., Any]] = field(default_factory=dict)

    def session(self) -> Session:
        return self.session_factory()


def build_services(settings: Settings) -> Services:
    client: redis.Redis = redis.Redis.from_url(settings.redis_url)
    clock: Clock = OffsetClock(client) if settings.dev_tools_enabled else SystemClock()
    clock_module.install(clock)
    secret = settings.mock_webhook_secret.get_secret_value()
    return Services(
        settings=settings,
        clock=clock,
        session_factory=get_session_factory(),
        redis=client,
        store=S3ObjectStore(settings),
        sms=build_sms(settings.sms_provider, client),
        payments=build_payments(
            settings.payment_providers,
            public_base_url=settings.public_base_url,
            secret=secret,
            failure_rate=settings.mock_provider_failure_rate,
            latency_ms=settings.mock_provider_latency_ms,
        ),
        couriers=build_couriers(
            settings.courier_providers,
            public_base_url=settings.public_base_url,
            secret=secret,
            client=client,
            failure_rate=settings.mock_provider_failure_rate,
            latency_ms=settings.mock_provider_latency_ms,
        ),
        push=build_push(settings.push_provider, settings.fcm_credentials_file, client),
        scanner=ClamdScanner(settings.clamav_host, settings.clamav_port)
        if settings.clamav_enabled
        else None,
        id_tokens=(
            GoogleIdTokenVerifier(settings.google_oauth_client_ids)
            if settings.google_oauth_client_ids or settings.is_production
            else FakeIdTokenVerifier()
        ),
        rate_limiter=RateLimiter(client),
        tasks=CeleryTaskQueue(),
    )
