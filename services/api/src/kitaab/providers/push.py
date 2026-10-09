"""Push notifications: Firebase Cloud Messaging, and a fake for development and tests."""

import json
import logging
from dataclasses import dataclass, field
from typing import Any, Protocol

import redis

log = logging.getLogger(__name__)
OUTBOX_KEY = "kitaab:dev:push_outbox"


@dataclass(frozen=True)
class PushMessage:
    title: str
    body: str
    data: dict[str, str] = field(default_factory=dict)


class PushProvider(Protocol):
    name: str

    def send(self, tokens: list[str], message: PushMessage) -> list[str]:
        """Send to each token. Returns the tokens the service reports as no longer valid."""
        ...


class FakePushProvider:
    name = "fake"

    def __init__(self, client: "redis.Redis | None" = None) -> None:
        self._redis = client
        self.sent: list[tuple[list[str], PushMessage]] = []
        self.invalid_tokens: set[str] = set()

    def send(self, tokens: list[str], message: PushMessage) -> list[str]:
        self.sent.append((tokens, message))
        if self._redis is not None:
            self._redis.lpush(
                OUTBOX_KEY,
                json.dumps({"tokens": len(tokens), "title": message.title, "data": message.data}),
            )
            self._redis.ltrim(OUTBOX_KEY, 0, 199)
        return [t for t in tokens if t in self.invalid_tokens]


class FcmPushProvider:
    """FCM through the official firebase-admin SDK. UNVERIFIED until tested
    with the owner's Firebase project (docs/INTEGRATIONS.md)."""

    name = "fcm"

    def __init__(self, credentials_file: str | None) -> None:
        import firebase_admin
        from firebase_admin import credentials

        cred = (
            credentials.Certificate(credentials_file)
            if credentials_file
            else credentials.ApplicationDefault()
        )
        self._app: Any = firebase_admin.initialize_app(cred, name="kitaab")

    def send(self, tokens: list[str], message: PushMessage) -> list[str]:
        from firebase_admin import messaging

        if not tokens:
            return []
        multicast = messaging.MulticastMessage(
            tokens=tokens,
            notification=messaging.Notification(title=message.title, body=message.body),
            data=message.data,
            android=messaging.AndroidConfig(priority="high"),
        )
        result = messaging.send_each_for_multicast(multicast, app=self._app)
        invalid = []
        for token, response in zip(tokens, result.responses, strict=True):
            if not response.success and isinstance(response.exception, messaging.UnregisteredError):
                invalid.append(token)
        log.info(
            "push sent", extra={"success": result.success_count, "failure": result.failure_count}
        )
        return invalid


def build_push(
    provider: str, credentials_file: str | None, client: "redis.Redis | None"
) -> PushProvider:
    if provider == "fcm":
        return FcmPushProvider(credentials_file)
    return FakePushProvider(client)
