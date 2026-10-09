"""Couriers. Status updates arrive by webhook where the courier supports it,
otherwise by a polling job; both paths are idempotent."""

import json
import random
import time
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Literal, Protocol, cast

import redis

from kitaab.providers import mock_signing
from kitaab.providers.errors import InvalidSignature, NotConfigured, ProviderError

CourierState = Literal[
    "BOOKED", "PICKED_UP", "IN_TRANSIT", "OUT_FOR_DELIVERY", "DELIVERED", "FAILED", "RETURNED"
]


@dataclass(frozen=True)
class Shipment:
    order_code: str
    recipient_name: str
    recipient_phone_e164: str
    city_name: str
    address: str
    landmark: str
    cod_amount_paisa: int
    pieces: int


@dataclass(frozen=True)
class Consignment:
    cn_number: str
    tracking_url: str | None


@dataclass(frozen=True)
class CourierEvent:
    event_id: str
    cn_number: str
    state: CourierState
    description: str
    occurred_at: datetime | None = None


class CourierProvider(Protocol):
    code: str
    name: str
    has_api: bool
    supports_webhooks: bool

    def create_consignment(self, shipment: Shipment) -> Consignment: ...
    def fetch_events(self, cn_number: str) -> list[CourierEvent]: ...
    def parse_webhook(self, headers: dict[str, str], body: bytes) -> list[CourierEvent]: ...


class MockCourierProvider:
    """Books fake consignments and reports statuses kept in Redis. The dev API
    (`POST /api/v1/_dev/mock-courier/{cn}/events`) advances a parcel and the mock
    posts a signed webhook to the API, like a real courier would."""

    code = "mock"
    name = "Mock Courier"
    has_api = True
    supports_webhooks = True

    def __init__(
        self,
        *,
        public_base_url: str,
        secret: str,
        client: "redis.Redis | None",
        failure_rate: float = 0.0,
        latency_ms: int = 0,
    ) -> None:
        self.public_base_url = public_base_url.rstrip("/")
        self.secret = secret
        self._redis = client
        self.failure_rate = failure_rate
        self.latency_ms = latency_ms
        self._memory: dict[str, list[CourierEvent]] = {}

    def _simulate_network(self) -> None:
        if self.latency_ms:
            time.sleep(self.latency_ms / 1000 * random.uniform(0.5, 1.5))  # noqa: S311
        if self.failure_rate and random.random() < self.failure_rate:  # noqa: S311
            raise ProviderError("mock courier: simulated failure")

    def create_consignment(self, shipment: Shipment) -> Consignment:
        self._simulate_network()
        cn = f"MOCK-{random.randint(100000, 999999)}"  # noqa: S311
        self.record(
            CourierEvent(
                event_id=uuid.uuid4().hex, cn_number=cn, state="BOOKED", description="Booked"
            )
        )
        return Consignment(
            cn_number=cn, tracking_url=f"{self.public_base_url}/mock/couriers/track/{cn}"
        )

    def _key(self, cn: str) -> str:
        return f"kitaab:dev:courier:{cn}"

    def record(self, event: CourierEvent) -> None:
        payload = json.dumps(
            {
                "event_id": event.event_id,
                "cn": event.cn_number,
                "state": event.state,
                "description": event.description,
            }
        )
        if self._redis is not None:
            self._redis.rpush(self._key(event.cn_number), payload)
            self._redis.expire(self._key(event.cn_number), 30 * 86400)
        else:
            self._memory.setdefault(event.cn_number, []).append(event)

    def fetch_events(self, cn_number: str) -> list[CourierEvent]:
        if self._redis is None:
            return list(self._memory.get(cn_number, []))
        return [
            CourierEvent(
                event_id=d["event_id"],
                cn_number=d["cn"],
                state=d["state"],
                description=d["description"],
            )
            for d in (
                json.loads(raw)
                for raw in cast(list[bytes], self._redis.lrange(self._key(cn_number), 0, -1))
            )
        ]

    def build_webhook(
        self, cn_number: str, state: CourierState, description: str
    ) -> tuple[bytes, dict[str, str]]:
        event = CourierEvent(
            event_id=uuid.uuid4().hex, cn_number=cn_number, state=state, description=description
        )
        self.record(event)
        body = json.dumps(
            {
                "events": [
                    {
                        "event_id": event.event_id,
                        "cn": cn_number,
                        "state": state,
                        "description": description,
                    }
                ]
            }
        ).encode()
        return body, mock_signing.sign(self.secret, body)

    def parse_webhook(self, headers: dict[str, str], body: bytes) -> list[CourierEvent]:
        if not mock_signing.verify(self.secret, headers, body):
            raise InvalidSignature("mock courier webhook signature")
        return [
            CourierEvent(
                event_id=str(e["event_id"]),
                cn_number=str(e["cn"]),
                state=e["state"],
                description=str(e.get("description", "")),
            )
            for e in json.loads(body)["events"]
        ]


class ManualCourier:
    """For couriers without an integration: the admin types the CN."""

    code = "manual"
    name = "Other courier (enter CN)"
    has_api = False
    supports_webhooks = False

    def create_consignment(self, shipment: Shipment) -> Consignment:
        raise ProviderError("Enter the CN number for this courier")

    def fetch_events(self, cn_number: str) -> list[CourierEvent]:
        return []

    def parse_webhook(self, headers: dict[str, str], body: bytes) -> list[CourierEvent]:
        raise InvalidSignature("manual courier has no webhooks")


class UnconfiguredCourier:
    """Skeleton for Trax, Leopards or TCS until the owner supplies official API
    documentation in docs/integrations/<code>/ (docs/INTEGRATIONS.md)."""

    has_api = True
    supports_webhooks = False

    def __init__(self, code: str, name: str) -> None:
        self.code = code
        self.name = name

    def create_consignment(self, shipment: Shipment) -> Consignment:
        raise NotConfigured(f"courier '{self.code}'")

    def fetch_events(self, cn_number: str) -> list[CourierEvent]:
        raise NotConfigured(f"courier '{self.code}'")

    def parse_webhook(self, headers: dict[str, str], body: bytes) -> list[CourierEvent]:
        raise NotConfigured(f"courier '{self.code}'")


REAL_COURIERS = {"trax": "Trax", "leopards": "Leopards Courier", "tcs": "TCS"}


class CourierRegistry:
    def __init__(self, couriers: list[CourierProvider]) -> None:
        self._by_code = {c.code: c for c in couriers}

    def get(self, code: str) -> CourierProvider | None:
        return self._by_code.get(code)

    def all(self) -> list[CourierProvider]:
        return list(self._by_code.values())

    def name_of(self, code: str | None) -> str:
        courier = self._by_code.get(code or "")
        return courier.name if courier else (code or "")


def build_couriers(
    codes: list[str],
    *,
    public_base_url: str,
    secret: str,
    client: "redis.Redis | None",
    failure_rate: float,
    latency_ms: int,
) -> CourierRegistry:
    couriers: list[CourierProvider] = []
    for code in codes:
        if code == "mock":
            couriers.append(
                MockCourierProvider(
                    public_base_url=public_base_url,
                    secret=secret,
                    client=client,
                    failure_rate=failure_rate,
                    latency_ms=latency_ms,
                )
            )
        elif code in REAL_COURIERS:
            couriers.append(UnconfiguredCourier(code, REAL_COURIERS[code]))
    couriers.append(ManualCourier())
    return CourierRegistry(couriers)
