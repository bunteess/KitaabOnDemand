"""SMS gateway. The mock keeps an outbox in Redis for development and tests."""

import json
import logging
from typing import Protocol, cast

import redis

from kitaab.phone import mask_phone
from kitaab.providers.errors import NotConfigured

log = logging.getLogger(__name__)
OUTBOX_KEY = "kitaab:dev:sms_outbox"


class SmsProvider(Protocol):
    name: str

    def send(self, to_e164: str, text: str) -> None: ...


class MockSmsProvider:
    """Writes messages to a Redis list readable through the dev API. Nothing is sent."""

    name = "mock"

    def __init__(self, client: "redis.Redis | None") -> None:
        self._redis = client
        self.sent: list[tuple[str, str]] = []

    def send(self, to_e164: str, text: str) -> None:
        self.sent.append((to_e164, text))
        if self._redis is not None:
            self._redis.lpush(OUTBOX_KEY, json.dumps({"to": to_e164, "text": text}))
            self._redis.ltrim(OUTBOX_KEY, 0, 199)
        log.info("mock sms queued", extra={"to": mask_phone(to_e164)})

    def outbox(self, phone: str | None = None) -> list[dict[str, str]]:
        if self._redis is None:
            return [
                {"to": to, "text": text} for to, text in reversed(self.sent) if phone in (None, to)
            ]
        raw_items = cast(list[bytes], self._redis.lrange(OUTBOX_KEY, 0, 199))
        items = [json.loads(raw) for raw in raw_items]
        return [item for item in items if phone in (None, item["to"])]


class UnconfiguredSmsProvider:
    """Placeholder for the owner's chosen gateway (docs/integrations/<provider>/)."""

    def __init__(self, name: str) -> None:
        self.name = name

    def send(self, to_e164: str, text: str) -> None:
        raise NotConfigured(f"SMS gateway '{self.name}'")


def build_sms(provider: str, client: "redis.Redis | None") -> SmsProvider:
    if provider == "mock":
        return MockSmsProvider(client)
    return UnconfiguredSmsProvider(provider)
