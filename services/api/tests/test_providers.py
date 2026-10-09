"""Provider adapters: ClamAV over a fake clamd, SMS, push, Google ID tokens,
mock signing, courier polling and the unconfigured skeletons (which must
refuse rather than guess at an API)."""

import socket
import struct
import threading
import uuid
from pathlib import Path
from typing import Any

import pytest

from kitaab.domain.enums import PaymentMethod
from kitaab.providers import mock_signing
from kitaab.providers.antivirus import ClamdScanner, ScanError
from kitaab.providers.courier import (
    CourierEvent,
    CourierRegistry,
    ManualCourier,
    MockCourierProvider,
    Shipment,
    UnconfiguredCourier,
    build_couriers,
)
from kitaab.providers.errors import InvalidSignature, NotConfigured, ProviderError
from kitaab.providers.id_tokens import GoogleIdTokenVerifier, InvalidIdToken
from kitaab.providers.payment import (
    MockPaymentProvider,
    UnconfiguredPaymentProvider,
    build_payments,
)
from kitaab.providers.push import FakePushProvider, PushMessage, build_push
from kitaab.providers.sms import MockSmsProvider, UnconfiguredSmsProvider, build_sms
from support import Api

SHIPMENT = Shipment("KD123", "A", "+923001234567", "Lahore", "House 1", "Park", 0, 1)


# -- ClamAV ---------------------------------------------------------------------------


class _FakeClamd:
    """Speaks just enough of clamd's INSTREAM protocol."""

    def __init__(self, reply: bytes) -> None:
        self.reply = reply
        self.received = b""
        self.server = socket.create_server(("127.0.0.1", 0))
        self.port = self.server.getsockname()[1]
        self.thread = threading.Thread(target=self._serve, daemon=True)
        self.thread.start()

    def _serve(self) -> None:
        conn, _ = self.server.accept()
        with conn:
            assert conn.recv(10) == b"zINSTREAM\0"
            while True:
                size = struct.unpack("!L", self._read(conn, 4))[0]
                if size == 0:
                    break
                self.received += self._read(conn, size)
            conn.sendall(self.reply)

    @staticmethod
    def _read(conn: socket.socket, n: int) -> bytes:
        data = b""
        while len(data) < n:
            data += conn.recv(n - len(data))
        return data

    def close(self) -> None:
        self.server.close()


@pytest.fixture
def pdf_file(tmp_path: Path) -> Path:
    path = tmp_path / "f.pdf"
    path.write_bytes(b"%PDF-1.7 test body")
    return path


@pytest.mark.parametrize(
    ("reply", "clean", "signature"),
    [
        (b"stream: OK\0", True, None),
        (b"stream: Eicar-Signature FOUND\0", False, "Eicar-Signature"),
    ],
)
def test_clamd_results(pdf_file: Path, reply: bytes, clean: bool, signature: str | None) -> None:
    clamd = _FakeClamd(reply)
    try:
        result = ClamdScanner("127.0.0.1", clamd.port, timeout=5).scan_file(pdf_file)
    finally:
        clamd.close()
    assert result.clean is clean
    assert result.signature == signature
    assert clamd.received == b"%PDF-1.7 test body"


def test_clamd_errors(pdf_file: Path) -> None:
    clamd = _FakeClamd(b"stream: INSTREAM size limit exceeded. ERROR\0")
    try:
        with pytest.raises(ScanError):
            ClamdScanner("127.0.0.1", clamd.port, timeout=5).scan_file(pdf_file)
    finally:
        clamd.close()
    with pytest.raises(ScanError):
        ClamdScanner("127.0.0.1", 1, timeout=1).scan_file(pdf_file)


# -- SMS and push ---------------------------------------------------------------------


def test_sms_providers() -> None:
    mock = build_sms("mock", None)
    assert isinstance(mock, MockSmsProvider)
    mock.send("+923001234567", "hello")
    mock.send("+923111234567", "other")
    assert mock.outbox("+923001234567") == [{"to": "+923001234567", "text": "hello"}]
    assert len(mock.outbox()) == 2
    real = build_sms("telenor", None)
    assert isinstance(real, UnconfiguredSmsProvider)
    with pytest.raises(NotConfigured) as error:
        real.send("+923001234567", "hello")
    assert "docs/INTEGRATIONS.md" in str(error.value)
    assert error.value.public_message == "SMS gateway 'telenor' is not set up yet"


@pytest.mark.integration
def test_sms_outbox_in_redis(redis_client: Any) -> None:
    sms = MockSmsProvider(redis_client)
    sms.send("+923001234567", "one")
    assert sms.outbox("+923001234567") == [{"to": "+923001234567", "text": "one"}]


@pytest.mark.integration
def test_push_outbox_in_redis(redis_client: Any) -> None:
    push = build_push("fake", None, redis_client)
    assert isinstance(push, FakePushProvider)
    with pytest.raises(ValueError, match="PUSH_PROVIDER 'fmc'"):
        build_push("fmc", None, redis_client)
    push.invalid_tokens.add("gone")
    assert push.send(["ok", "gone"], PushMessage("T", "B", {"k": "v"})) == ["gone"]
    assert redis_client.llen("kitaab:dev:push_outbox") == 1


# -- Google ---------------------------------------------------------------------------


def _verifier(monkeypatch: pytest.MonkeyPatch, claims: dict[str, Any] | Exception) -> Any:
    from google.oauth2 import id_token

    def fake_verify(token: str, request: object, audience: object = None) -> dict[str, Any]:
        if isinstance(claims, Exception):
            raise claims
        return claims

    monkeypatch.setattr(id_token, "verify_oauth2_token", fake_verify)
    return GoogleIdTokenVerifier(["app-client-id"])


def test_google_tokens_are_checked_for_audience_and_issuer(monkeypatch: pytest.MonkeyPatch) -> None:
    good = {
        "aud": "app-client-id",
        "iss": "https://accounts.google.com",
        "sub": "123",
        "email": "a@example.com",
        "email_verified": True,
        "name": "A",
    }
    identity = _verifier(monkeypatch, good).verify("t")
    assert (identity.subject, identity.email, identity.name) == ("123", "a@example.com", "A")
    unverified = _verifier(monkeypatch, {**good, "email_verified": False}).verify("t")
    assert unverified.email is None
    for bad in ({**good, "aud": "someone-else"}, {**good, "iss": "evil.example"}):
        with pytest.raises(InvalidIdToken):
            _verifier(monkeypatch, bad).verify("t")
    with pytest.raises(InvalidIdToken):
        _verifier(monkeypatch, ValueError("expired")).verify("t")
    with pytest.raises(InvalidIdToken):
        GoogleIdTokenVerifier([]).verify("t")


# -- signing --------------------------------------------------------------------------


def test_mock_signatures() -> None:
    headers = mock_signing.sign("s3cret", b"body", timestamp=1000)
    assert mock_signing.verify("s3cret", headers, b"body", now=1000)
    assert mock_signing.verify("s3cret", {k.upper(): v for k, v in headers.items()}, b"body", 1000)
    assert not mock_signing.verify("other", headers, b"body", now=1000)
    assert not mock_signing.verify("s3cret", headers, b"body!", now=1000)
    assert not mock_signing.verify("s3cret", headers, b"body", now=1000 + 301)
    assert not mock_signing.verify("s3cret", {**headers, "x-mock-timestamp": "x"}, b"body")


# -- payments and couriers ------------------------------------------------------------


def test_payment_registry() -> None:
    registry = build_payments(
        ["mock", "jazzcash"],
        public_base_url="http://x/",
        secret="s",
        failure_rate=0,
        latency_ms=0,
    )
    assert isinstance(registry.get("mock"), MockPaymentProvider)
    assert registry.get("unknown") is None
    assert registry.enabled_methods() == set(PaymentMethod)
    cod_only = build_payments([], public_base_url="", secret="", failure_rate=0, latency_ms=0)
    assert cod_only.enabled_methods() == {PaymentMethod.COD}
    assert cod_only.for_method(PaymentMethod.CARD) is None
    with pytest.raises(ValueError, match="'easypasia'"):
        build_payments(["easypasia"], public_base_url="", secret="", failure_rate=0, latency_ms=0)


def test_unconfigured_gateways_refuse() -> None:
    gateway = UnconfiguredPaymentProvider("card", frozenset({PaymentMethod.CARD}))
    with pytest.raises(NotConfigured):
        gateway.create_checkout(
            payment_id=uuid.uuid4(), amount_paisa=1, order_code="KD", return_url=""
        )
    with pytest.raises(NotConfigured):
        gateway.parse_webhook({}, b"")
    with pytest.raises(ProviderError):
        gateway.refund("ref", 1)


def test_mock_gateway_failure_simulation() -> None:
    flaky = MockPaymentProvider(public_base_url="http://x", secret="s", failure_rate=1.0)
    with pytest.raises(ProviderError):
        flaky.create_checkout(
            payment_id=uuid.uuid4(), amount_paisa=1, order_code="KD", return_url=""
        )
    slow = MockPaymentProvider(public_base_url="http://x", secret="s", latency_ms=1)
    assert slow.refund("ref", 1).startswith("mockrefund_")


def test_couriers() -> None:
    registry = build_couriers(
        ["mock", "leopards", "tcs"],
        public_base_url="http://x",
        secret="s",
        client=None,
        failure_rate=0,
        latency_ms=0,
    )
    assert [c.code for c in registry.all()] == ["mock", "leopards", "tcs", "manual"]
    assert registry.name_of("tcs") == "TCS"
    assert registry.name_of("gone") == "gone"
    assert registry.name_of(None) == ""
    unconfigured = UnconfiguredCourier("tcs", "TCS")
    for call in (
        lambda: unconfigured.create_consignment(SHIPMENT),
        lambda: unconfigured.fetch_events("CN"),
        lambda: unconfigured.parse_webhook({}, b""),
    ):
        with pytest.raises(NotConfigured):
            call()
    manual = ManualCourier()
    with pytest.raises(ProviderError):
        manual.create_consignment(SHIPMENT)
    with pytest.raises(ValueError, match="'fedex'"):
        build_couriers(
            ["fedex"], public_base_url="", secret="", client=None, failure_rate=0, latency_ms=0
        )
    assert manual.fetch_events("CN") == []
    with pytest.raises(InvalidSignature):
        manual.parse_webhook({}, b"")
    flaky = MockCourierProvider(public_base_url="", secret="s", client=None, failure_rate=1.0)
    with pytest.raises(ProviderError):
        flaky.create_consignment(SHIPMENT)


@pytest.mark.integration
def test_mock_courier_events_in_redis(redis_client: Any) -> None:
    courier = MockCourierProvider(public_base_url="http://x", secret="s", client=redis_client)
    cn = courier.create_consignment(SHIPMENT).cn_number
    courier.build_webhook(cn, "IN_TRANSIT", "On the way")
    assert [e.state for e in courier.fetch_events(cn)] == ["BOOKED", "IN_TRANSIT"]


class _PollingCourier:
    """A courier with an API but no webhooks: statuses come from polling."""

    code = "poller"
    name = "Polling Courier"
    has_api = True
    supports_webhooks = False

    def __init__(self) -> None:
        self.events: dict[str, list[CourierEvent]] = {}
        self.fail = False

    def create_consignment(self, shipment: Shipment) -> Any:
        from kitaab.providers.courier import Consignment

        return Consignment("POLL-1", None)

    def fetch_events(self, cn_number: str) -> list[CourierEvent]:
        if self.fail:
            raise ProviderError("down")
        return self.events.get(cn_number, [])

    def parse_webhook(self, headers: dict[str, str], body: bytes) -> list[CourierEvent]:
        raise InvalidSignature("no webhooks")


@pytest.fixture
def poller(api: Api) -> _PollingCourier:
    courier = _PollingCourier()
    registry = api.services.couriers
    api.services.couriers = CourierRegistry([*registry.all(), courier])
    return courier


@pytest.mark.integration
def test_polling_couriers(api: Api, poller: _PollingCourier) -> None:
    customer = api.customer()
    admin = api.admin()
    order = api.print_order(customer)
    for action, body in (
        ("start-verification", {}),
        ("approve", {"vendor_id": str(api.vendor()), "vendor_cost_paisa": 1}),
        ("start-printing", {}),
        ("ready-for-dispatch", {}),
        ("dispatch", {"courier_code": "poller"}),
    ):
        api.admin_action(admin, order["id"], action, body)
    poller.fail = True
    assert api.post("/api/v1/_dev/jobs/poll_courier_status").json()["result"] == 0
    poller.fail = False
    poller.events["POLL-1"] = [
        CourierEvent("e1", "POLL-1", "IN_TRANSIT", "In transit"),
        CourierEvent("e2", "UNKNOWN-CN", "DELIVERED", "Delivered"),
    ]
    assert api.post("/api/v1/_dev/jobs/poll_courier_status").json()["result"] == 1
    poller.events["POLL-1"].append(CourierEvent("e3", "POLL-1", "DELIVERED", "Delivered"))
    # Already-seen events are skipped; the new one delivers the order.
    assert api.post("/api/v1/_dev/jobs/poll_courier_status").json()["result"] == 1
    assert api.get(f"/api/v1/orders/{order['id']}", customer).json()["status"] == "DELIVERED"
    assert api.post("/api/v1/_dev/jobs/poll_courier_status").json()["result"] == 0
