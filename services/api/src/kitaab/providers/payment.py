"""Payment gateways. Card data never reaches our servers: every gateway uses a
hosted checkout page, and the result arrives by a signed webhook."""

import json
import random
import time
import uuid
from dataclasses import dataclass
from typing import Literal, Protocol

from kitaab.domain.enums import PaymentMethod
from kitaab.providers import mock_signing
from kitaab.providers.errors import (
    InvalidSignature,
    NotConfigured,
    ProviderError,
    RefundNotSupported,
)


@dataclass(frozen=True)
class CheckoutSession:
    provider_ref: str
    checkout_url: str


@dataclass(frozen=True)
class PaymentEvent:
    event_id: str
    provider_ref: str
    status: Literal["PAID", "FAILED"]
    amount_paisa: int | None
    failure_reason: str | None = None


class PaymentProvider(Protocol):
    code: str
    methods: frozenset[PaymentMethod]

    def create_checkout(
        self, *, payment_id: uuid.UUID, amount_paisa: int, order_code: str, return_url: str
    ) -> CheckoutSession: ...

    def parse_webhook(self, headers: dict[str, str], body: bytes) -> PaymentEvent:
        """Verify the signature and parse the event. Raises InvalidSignature."""
        ...

    def refund(self, provider_ref: str, amount_paisa: int) -> str:
        """Refund through the gateway; returns its reference. Raises RefundNotSupported."""
        ...


class MockPaymentProvider:
    """Imitates a hosted checkout. The page at /mock/payments/{ref} lets the
    tester pay or fail, then posts a signed webhook back to the API."""

    code = "mock"
    methods = frozenset({PaymentMethod.EASYPAISA, PaymentMethod.JAZZCASH, PaymentMethod.CARD})

    def __init__(
        self, *, public_base_url: str, secret: str, failure_rate: float = 0.0, latency_ms: int = 0
    ) -> None:
        self.public_base_url = public_base_url.rstrip("/")
        self.secret = secret
        self.failure_rate = failure_rate
        self.latency_ms = latency_ms

    def _simulate_network(self) -> None:
        if self.latency_ms:
            time.sleep(self.latency_ms / 1000 * random.uniform(0.5, 1.5))  # noqa: S311
        if self.failure_rate and random.random() < self.failure_rate:  # noqa: S311
            raise ProviderError("mock gateway: simulated failure")

    def create_checkout(
        self, *, payment_id: uuid.UUID, amount_paisa: int, order_code: str, return_url: str
    ) -> CheckoutSession:
        self._simulate_network()
        ref = f"mockpay_{uuid.uuid4().hex[:20]}"
        return CheckoutSession(
            provider_ref=ref, checkout_url=f"{self.public_base_url}/mock/payments/{ref}"
        )

    def build_webhook(
        self, provider_ref: str, status: Literal["PAID", "FAILED"], amount_paisa: int
    ) -> tuple[bytes, dict[str, str]]:
        body = json.dumps(
            {
                "event_id": f"evt_{uuid.uuid4().hex}",
                "ref": provider_ref,
                "status": status,
                "amount_paisa": amount_paisa,
                "reason": None if status == "PAID" else "Declined by mock gateway",
            }
        ).encode()
        return body, mock_signing.sign(self.secret, body)

    def parse_webhook(self, headers: dict[str, str], body: bytes) -> PaymentEvent:
        if not mock_signing.verify(self.secret, headers, body):
            raise InvalidSignature("mock payment webhook signature")
        data = json.loads(body)
        return PaymentEvent(
            event_id=str(data["event_id"]),
            provider_ref=str(data["ref"]),
            status="PAID" if data["status"] == "PAID" else "FAILED",
            amount_paisa=int(data["amount_paisa"])
            if data.get("amount_paisa") is not None
            else None,
            failure_reason=data.get("reason"),
        )

    def refund(self, provider_ref: str, amount_paisa: int) -> str:
        self._simulate_network()
        return f"mockrefund_{uuid.uuid4().hex[:16]}"


class UnconfiguredPaymentProvider:
    """Skeleton for a real gateway. Built only from official documentation in
    docs/integrations/<code>/ (docs/INTEGRATIONS.md)."""

    def __init__(self, code: str, methods: frozenset[PaymentMethod]) -> None:
        self.code = code
        self.methods = methods

    def create_checkout(
        self, *, payment_id: uuid.UUID, amount_paisa: int, order_code: str, return_url: str
    ) -> CheckoutSession:
        raise NotConfigured(f"payment gateway '{self.code}'")

    def parse_webhook(self, headers: dict[str, str], body: bytes) -> PaymentEvent:
        raise NotConfigured(f"payment gateway '{self.code}'")

    def refund(self, provider_ref: str, amount_paisa: int) -> str:
        raise RefundNotSupported(f"payment gateway '{self.code}' is not configured")


REAL_GATEWAYS: dict[str, frozenset[PaymentMethod]] = {
    "easypaisa": frozenset({PaymentMethod.EASYPAISA}),
    "jazzcash": frozenset({PaymentMethod.JAZZCASH}),
    "card": frozenset({PaymentMethod.CARD}),
}


class PaymentRegistry:
    def __init__(self, providers: list[PaymentProvider]) -> None:
        self._by_code = {p.code: p for p in providers}

    def get(self, code: str) -> PaymentProvider | None:
        return self._by_code.get(code)

    def for_method(self, method: PaymentMethod) -> PaymentProvider | None:
        return next((p for p in self._by_code.values() if method in p.methods), None)

    def enabled_methods(self) -> set[PaymentMethod]:
        methods = {PaymentMethod.COD}
        for provider in self._by_code.values():
            methods |= provider.methods
        return methods


def build_payments(
    codes: list[str], *, public_base_url: str, secret: str, failure_rate: float, latency_ms: int
) -> PaymentRegistry:
    providers: list[PaymentProvider] = []
    for code in codes:
        if code == "mock":
            providers.append(
                MockPaymentProvider(
                    public_base_url=public_base_url,
                    secret=secret,
                    failure_rate=failure_rate,
                    latency_ms=latency_ms,
                )
            )
        elif code in REAL_GATEWAYS:
            providers.append(UnconfiguredPaymentProvider(code, REAL_GATEWAYS[code]))
    return PaymentRegistry(providers)
