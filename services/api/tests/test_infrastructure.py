"""Cross-cutting plumbing: problem responses, middleware, logging, the clock
and the application factory."""

import json
import logging
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

import pytest
import redis
from fastapi import APIRouter
from fastapi.testclient import TestClient

from kitaab import clock as clock_module
from kitaab.clock import FrozenClock, OffsetClock, SystemClock
from kitaab.config import Environment, Settings
from kitaab.logging import JsonFormatter, PiiFilter, configure_logging, request_id_var, scrub
from kitaab.main import create_app
from kitaab.middleware import MAX_BODY_BYTES
from support import Api


def test_unknown_routes_and_methods_are_problems(api: Api) -> None:
    missing = api.client.get("/api/v1/nope")
    assert missing.status_code == 404
    assert missing.headers["content-type"] == "application/problem+json"
    assert missing.json()["code"] == "not-found"
    wrong = api.client.delete("/api/v1/cities")
    assert wrong.status_code == 405
    assert wrong.json()["code"] == "method-not-allowed"


def test_unexpected_errors_hide_internals(api: Api) -> None:
    router = APIRouter()

    @router.get("/boom")
    def boom() -> None:
        raise RuntimeError("secret database password in this message")

    api.app.include_router(router)
    client = TestClient(api.app, raise_server_exceptions=False)
    response = client.get("/boom")
    assert response.status_code == 500
    assert response.json()["code"] == "internal-error"
    assert "secret" not in response.text


@pytest.mark.integration
def test_security_headers_and_request_ids(api: Api) -> None:
    response = api.client.get("/api/v1/cities", headers={"X-Request-ID": "abcdef123456"})
    assert response.headers["X-Request-ID"] == "abcdef123456"
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert response.headers["Cache-Control"] == "no-store"
    assert "default-src 'none'" in response.headers["Content-Security-Policy"]
    assert "Strict-Transport-Security" not in response.headers
    generated = api.client.get("/healthz", headers={"X-Request-ID": "short"})
    assert len(generated.headers["X-Request-ID"]) == 32
    docs = api.client.get("/docs")
    assert "Content-Security-Policy" not in docs.headers


def _production_settings() -> Settings:
    # Skips the production safety check, which the test settings would fail.
    return Settings.model_construct(**{**dict(Settings()), "environment": Environment.PRODUCTION})


def test_production_apps_send_hsts_and_hide_the_docs() -> None:
    app = create_app(settings=_production_settings())
    response = TestClient(app).get("/healthz")
    assert response.headers["Strict-Transport-Security"].startswith("max-age=31536000")
    assert app.openapi_url is None
    assert app.docs_url is None
    assert TestClient(app).get("/openapi.json").status_code == 404


@pytest.mark.integration
def test_cors_allows_only_the_configured_origins(api: Api) -> None:
    allowed = api.client.options(
        "/api/v1/cities",
        headers={"Origin": "http://localhost:5173", "Access-Control-Request-Method": "GET"},
    )
    assert allowed.headers["access-control-allow-origin"] == "http://localhost:5173"
    denied = api.client.options(
        "/api/v1/cities",
        headers={"Origin": "https://evil.example", "Access-Control-Request-Method": "GET"},
    )
    assert "access-control-allow-origin" not in denied.headers


@pytest.mark.integration
def test_large_bodies_are_refused(api: Api) -> None:
    big = b"{" + b" " * (MAX_BODY_BYTES + 10) + b"}"
    declared = api.client.post(
        "/api/v1/auth/otp/request", content=big, headers={"Content-Type": "application/json"}
    )
    assert declared.status_code == 413
    assert declared.json()["code"] == "payload-too-large"

    def chunks() -> Iterator[bytes]:
        for _ in range(20):
            yield b" " * (MAX_BODY_BYTES // 10)

    streamed = api.client.post("/api/v1/webhooks/payments/mock", content=chunks())
    assert streamed.status_code == 413


@pytest.mark.integration
def test_readiness(api: Api) -> None:
    ok = api.client.get("/readyz")
    assert ok.json() == {"status": "ok", "database": "ok", "redis": "ok"}
    api.services.redis = redis.Redis.from_url("redis://localhost:1/0", socket_timeout=0.2)

    def broken() -> object:
        raise RuntimeError("database down")

    api.services.session_factory = broken  # type: ignore[assignment]
    down = api.client.get("/readyz")
    assert down.status_code == 503
    assert down.json() == {"status": "error", "database": "error", "redis": "error"}


def test_production_app_factory(monkeypatch: pytest.MonkeyPatch) -> None:
    import kitaab.main as main

    built: list[Settings] = []

    def fake_build(settings: Settings) -> object:
        built.append(settings)
        return None

    monkeypatch.setattr(main, "build_services", fake_build)
    monkeypatch.setattr(main, "configure_logging", lambda level: None)
    app = main.create_production_app()
    assert built
    assert app.openapi_url == "/openapi.json"


# -- logging --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("raw", "hidden"),
    [
        ("call 03001234567 now", "1234567"),
        ("call +92 300 1234567", "1234567"),
        ("call 0300-1234567", "1234567"),
        ("write to ayesha.khan@example.com", "ayesha"),
    ],
)
def test_scrub_masks_phones_and_emails(raw: str, hidden: str) -> None:
    assert hidden not in scrub(raw)


def test_scrub_leaves_other_numbers() -> None:
    assert scrub("order KD12345 total 125000 paisa") == "order KD12345 total 125000 paisa"


def test_json_logs_carry_the_request_id_and_hide_personal_data() -> None:
    record = logging.LogRecord(
        "kitaab.test", logging.INFO, __file__, 1, "sent to %s", ("03001234567",), None
    )
    record.phone = "+923001234567"
    record.count = 3
    PiiFilter().filter(record)
    token = request_id_var.set("req-123")
    try:
        payload = json.loads(JsonFormatter().format(record))
    finally:
        request_id_var.reset(token)
    assert payload["request_id"] == "req-123"
    assert "1234567" not in payload["msg"]
    assert "1234567" not in payload["phone"]
    assert payload["count"] == 3
    try:
        raise ValueError("bad 03001234567")
    except ValueError:
        import sys

        error = logging.LogRecord("x", logging.ERROR, __file__, 1, "failed", None, sys.exc_info())
    assert "1234567" not in json.loads(JsonFormatter().format(error))["exc"]


def test_configure_logging() -> None:
    root = logging.getLogger()
    before = (list(root.handlers), root.level)
    try:
        configure_logging("debug", json_output=False)
        assert root.level == logging.DEBUG
        assert logging.getLogger("uvicorn.access").disabled
        assert isinstance(root.handlers[0].filters[0], PiiFilter)
    finally:
        root.handlers, _ = before
        root.setLevel(before[1])


# -- clock ----------------------------------------------------------------------------


def test_frozen_clock() -> None:
    with pytest.raises(ValueError):
        FrozenClock(datetime(2026, 1, 1))  # noqa: DTZ001 (naive on purpose)
    frozen = FrozenClock(datetime(2026, 1, 1, tzinfo=UTC))
    frozen.advance(timedelta(hours=1))
    assert frozen.now() == datetime(2026, 1, 1, 1, tzinfo=UTC)
    frozen.set(datetime(2027, 1, 1, tzinfo=UTC))
    assert frozen.now().year == 2027


def test_system_clock_is_aware_and_installable() -> None:
    assert SystemClock().now().tzinfo is not None
    frozen = FrozenClock(datetime(2030, 1, 1, tzinfo=UTC))
    clock_module.install(frozen)
    try:
        assert clock_module.current() is frozen
        assert clock_module.utcnow() == datetime(2030, 1, 1, tzinfo=UTC)
    finally:
        clock_module.install(SystemClock())


@pytest.mark.integration
def test_offset_clock_shares_its_offset_through_redis(redis_client: "redis.Redis") -> None:
    writer = OffsetClock(redis_client)
    reader = OffsetClock(redis_client, cache_seconds=0)
    assert reader.offset_seconds() == 0
    writer.set_offset(7 * 86400)
    assert reader.offset_seconds() == 7 * 86400
    assert reader.now() - SystemClock().now() > timedelta(days=6, hours=23)
    # Redis going away keeps the last known offset.
    offline = OffsetClock(redis.Redis.from_url("redis://localhost:1/0", socket_timeout=0.2), 0)
    assert offline.offset_seconds() == 0


@pytest.mark.integration
def test_dev_clock_endpoints(api: Api, redis_client: "redis.Redis") -> None:
    # The harness clock is frozen: not adjustable over HTTP.
    assert api.client.get("/api/v1/_dev/clock").json()["offset_seconds"] == 0
    assert api.client.post("/api/v1/_dev/clock", json={"advance_seconds": 60}).status_code == 409
    api.services.clock = OffsetClock(redis_client, cache_seconds=0)
    moved = api.client.post("/api/v1/_dev/clock", json={"advance_seconds": 3600}).json()
    assert moved["offset_seconds"] == 3600
    again = api.client.post("/api/v1/_dev/clock", json={"offset_seconds": 0, "advance_seconds": 60})
    assert again.json()["offset_seconds"] == 60
    assert api.client.get("/api/v1/_dev/clock").json()["offset_seconds"] == 60


@pytest.mark.integration
def test_dev_outboxes(api: Api, redis_client: "redis.Redis") -> None:
    api.customer("03001234567")
    outbox = api.client.get("/api/v1/_dev/sms-outbox?phone=%2B923001234567").json()
    assert len(outbox) == 1
    assert outbox[0]["to"] == "+923001234567"
    assert api.client.get("/api/v1/_dev/push-outbox").json() == []


@pytest.mark.integration
def test_mock_pages(api: Api) -> None:
    unknown = api.client.get("/mock/payments/mockpay_unknown")
    assert "Unknown payment" in unknown.text
    done = api.client.post("/mock/payments/mockpay_unknown/complete", data={"outcome": "PAID"})
    assert "Unknown payment" in done.text
    customer = api.customer()
    admin = api.admin()
    order = api.print_order(customer)
    for action, body in (
        ("start-verification", {}),
        ("approve", {"vendor_id": str(api.vendor()), "vendor_cost_paisa": 1}),
        ("start-printing", {}),
        ("ready-for-dispatch", {}),
    ):
        api.admin_action(admin, order["id"], action, body)
    cn = api.admin_action(admin, order["id"], "dispatch", {"courier_code": "mock"})["tracking"][
        "cn_number"
    ]
    page = api.client.get(f"/mock/couriers/track/{cn}")
    assert cn in page.text
    assert "Booked" in page.text
    assert "No updates yet" in api.client.get("/mock/couriers/track/MOCK-000000").text


@pytest.mark.parametrize("error", ["timeout", "operational"])
def test_database_overload_returns_503(api: Api, error: str) -> None:
    from sqlalchemy.exc import OperationalError
    from sqlalchemy.exc import TimeoutError as PoolTimeout

    router = APIRouter()

    @router.get("/busy")
    def busy() -> None:
        if error == "timeout":
            raise PoolTimeout("QueuePool limit reached")
        raise OperationalError("SELECT 1", {}, Exception("connection refused"))

    api.app.include_router(router)
    response = TestClient(api.app, raise_server_exceptions=False).get("/busy")
    assert response.status_code == 503
    assert response.json()["code"] == "service-busy"
    assert response.headers["Retry-After"] == "5"
