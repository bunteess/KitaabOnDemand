"""CLI, OpenAPI export and worker wiring."""

from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest
from sqlalchemy import inspect

from kitaab import cli, openapi_export
from kitaab.db import get_engine
from kitaab.workers.celery_app import ping

if TYPE_CHECKING:
    from support import Api


@pytest.mark.integration
def test_migrate_command_upgrades_and_prepares_storage(capsys: pytest.CaptureFixture[str]) -> None:
    assert cli.main(["migrate", "--init-storage"]) == 0
    output = capsys.readouterr().out
    assert "migrated to head" in output
    assert "ready" in output
    assert "alembic_version" in inspect(get_engine()).get_table_names()


def test_openapi_export_writes_and_checks(tmp_path: Path) -> None:
    target = tmp_path / "openapi.json"
    assert openapi_export.main(["--check", str(target)]) == 1
    assert openapi_export.main([str(target)]) == 0
    assert openapi_export.main(["--check", str(target)]) == 0
    assert '"openapi"' in target.read_text()


def test_committed_contract_is_current() -> None:
    contract = Path(__file__).resolve().parents[3] / "packages" / "contracts" / "openapi.json"
    assert openapi_export.render() == contract.read_text(encoding="utf-8"), (
        "packages/contracts/openapi.json is stale: run 'make contracts'"
    )


def test_ping_task_runs_eagerly() -> None:
    assert ping.apply().get() == "pong"


# -- CLI ------------------------------------------------------------------------------


@pytest.mark.integration
def test_seed_is_idempotent_and_demo_logins_work(
    db: object, clock: object, capsys: pytest.CaptureFixture[str]
) -> None:
    assert cli.main(["seed", "--demo"]) == 0
    first = capsys.readouterr().out
    assert "cities: 20 added" in first
    assert "pricing: placeholder version 1 created" in first
    assert "admin@example.com" in first
    assert cli.main(["seed", "--demo"]) == 0
    second = capsys.readouterr().out
    assert "cities: 0 added" in second
    assert "pricing" not in second

    from sqlalchemy import func, select

    from kitaab.db import get_session_factory
    from kitaab.domain.enums import Role
    from kitaab.models import City, User

    with get_session_factory()() as session:
        assert session.scalar(select(func.count()).select_from(City)) == 20
        roles = sorted(r.value for r in session.scalars(select(User.role)))
    assert roles == ["ADMIN", "VENDOR"]
    assert Role.ADMIN.value in roles


@pytest.mark.integration
def test_seed_refuses_demo_logins_in_production(
    db: object, clock: object, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    from kitaab.config import Environment, Settings

    production = Settings.model_construct(
        **{**dict(Settings()), "environment": Environment.PRODUCTION}
    )
    monkeypatch.setattr(cli, "get_settings", lambda: production)
    assert cli.main(["seed", "--demo"]) == 1
    assert "Refusing" in capsys.readouterr().out


@pytest.mark.integration
def test_create_staff_commands(
    db: object, clock: object, capsys: pytest.CaptureFixture[str]
) -> None:
    assert cli.main(["create-admin", "owner@example.com", "Owner"]) == 0
    out = capsys.readouterr().out
    assert "Temporary password:" in out
    assert "otpauth://totp/" in out

    from kitaab.db import get_session_factory
    from kitaab.models import Vendor

    with get_session_factory()() as session:
        vendor = Vendor(name="CLI Press", contact_name="C", contact_phone_e164="+923211234567")
        session.add(vendor)
        session.commit()
        vendor_id = str(vendor.id)
    assert cli.main(["create-vendor-user", vendor_id, "press@example.com", "Press"]) == 0
    out = capsys.readouterr().out
    assert "Created vendor press@example.com" in out
    assert "otpauth" not in out
    missing = "00000000-0000-0000-0000-000000000000"
    assert cli.main(["create-vendor-user", missing, "x@example.com", "X"]) == 1


@pytest.mark.integration
def test_staff_recovery_commands(
    db: object, clock: object, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    assert cli.main(["create-admin", "boss@example.com", "Boss"]) == 0
    capsys.readouterr()
    assert cli.main(["reset-staff-login", "boss@example.com"]) == 0
    out = capsys.readouterr().out
    assert "every session signed out" in out
    assert "Temporary password:" in out
    assert "otpauth://totp/" in out
    assert cli.main(["reset-staff-login", "nobody@example.com"]) == 1

    from pydantic import SecretStr

    from kitaab.config import get_settings

    monkeypatch.delenv("OLD_DATA_ENCRYPTION_KEY", raising=False)
    assert cli.main(["rotate-encryption-key"]) == 1
    settings = get_settings()
    old_key = settings.data_encryption_key.get_secret_value()
    monkeypatch.setenv("OLD_DATA_ENCRYPTION_KEY", old_key)
    assert cli.main(["rotate-encryption-key"]) == 1
    assert "Set the new key first" in capsys.readouterr().out
    monkeypatch.setattr(settings, "data_encryption_key", SecretStr("rotated-key-" + "z" * 32))
    assert cli.main(["rotate-encryption-key"]) == 0
    assert "Re-encrypted 1 authenticator secrets" in capsys.readouterr().out
    # Running it again finds every secret already on the current key.
    assert cli.main(["rotate-encryption-key"]) == 0
    assert "0 authenticator secrets; 1 already" in capsys.readouterr().out


@pytest.mark.integration
def test_purge_command(db: object, clock: object, capsys: pytest.CaptureFixture[str]) -> None:
    assert cli.main(["purge", "--dry-run"]) == 0
    assert "dry_run=True" in capsys.readouterr().out


# -- workers and jobs -----------------------------------------------------------------


@pytest.mark.integration
def test_celery_tasks_call_the_jobs(api: "Api", monkeypatch: pytest.MonkeyPatch) -> None:
    from kitaab.workers import tasks

    monkeypatch.setattr(tasks, "services", lambda: api.services)
    assert tasks.expire_quotes.apply().get() == 0
    assert tasks.expire_pending_payments.apply().get() == 0
    assert tasks.poll_courier_status.apply().get() == 0
    assert tasks.purge_files.apply().get()["errors"] == 0
    missing = "00000000-0000-0000-0000-000000000000"
    tasks.validate_upload.apply(args=[missing]).get()
    tasks.deliver_notification.apply(args=[missing]).get()
    tasks.process_refund.apply(args=[missing]).get()
    sent: list[str] = []
    api.services.extras["http_post"] = lambda path, body, headers: sent.append(path)
    tasks.deliver_webhook.apply(args=["/x", "{}", {}]).get()
    assert sent == ["/x"]


def test_celery_queue_sends_by_name(monkeypatch: pytest.MonkeyPatch) -> None:
    from kitaab.container import CeleryTaskQueue
    from kitaab.workers.celery_app import app

    sent: list[tuple[str, dict[str, object]]] = []
    monkeypatch.setattr(app, "send_task", lambda name, kwargs: sent.append((name, kwargs)))
    CeleryTaskQueue().enqueue("purge_files", dry_run=True)
    assert sent == [("purge_files", {"dry_run": True})]


def test_inline_queue_needs_services() -> None:
    from kitaab.container import InlineTaskQueue

    with pytest.raises(RuntimeError):
        InlineTaskQueue().enqueue("purge_files")


def test_webhook_delivery_over_http(monkeypatch: pytest.MonkeyPatch) -> None:
    import httpx2

    from kitaab import jobs
    from kitaab.config import Settings

    calls: list[tuple[str, dict[str, str]]] = []

    class _Response:
        def __init__(self, status: int) -> None:
            self.status_code = status

    statuses = iter([200, 500])

    def fake_post(url: str, content: bytes, headers: dict[str, str], timeout: int) -> _Response:
        calls.append((url, headers))
        return _Response(next(statuses))

    monkeypatch.setattr(httpx2, "post", fake_post)

    class _Services:
        settings = Settings(internal_api_url="http://api:8000/")
        extras: dict[str, object] = {}

    services: Any = _Services()
    for _ in range(2):
        jobs.deliver_webhook(services, "/api/v1/webhooks/payments/mock", "{}", {"a": "b"})
    assert calls[0][0] == "http://api:8000/api/v1/webhooks/payments/mock"
    assert calls[0][1]["Content-Type"] == "application/json"


@pytest.mark.integration
def test_build_services_wires_the_configured_providers() -> None:
    from kitaab import clock as clock_module
    from kitaab.clock import OffsetClock, SystemClock
    from kitaab.config import Settings
    from kitaab.container import CeleryTaskQueue, build_services
    from kitaab.providers.antivirus import ClamdScanner
    from kitaab.providers.id_tokens import FakeIdTokenVerifier, GoogleIdTokenVerifier

    try:
        dev = build_services(Settings())
        assert isinstance(dev.clock, OffsetClock)
        assert isinstance(dev.tasks, CeleryTaskQueue)
        assert dev.scanner is None
        assert isinstance(dev.id_tokens, FakeIdTokenVerifier)
        live = build_services(
            Settings(
                dev_tools_enabled=False,
                clamav_enabled=True,
                google_oauth_client_ids=["abc.apps.googleusercontent.com"],
            )
        )
        assert isinstance(live.clock, SystemClock)
        assert isinstance(live.scanner, ClamdScanner)
        assert isinstance(live.id_tokens, GoogleIdTokenVerifier)
        with live.session() as session:
            assert session.is_active
    finally:
        clock_module.install(SystemClock())


@pytest.mark.integration
def test_validation_that_keeps_failing_rejects_the_upload(
    api: "Api", monkeypatch: pytest.MonkeyPatch
) -> None:
    from celery.exceptions import Retry

    from kitaab.domain import uploads
    from kitaab.workers import tasks
    from support import pdf_bytes

    customer = api.customer()
    api.tasks.eager = False
    upload = api.upload(customer, pdf_bytes(2))
    assert upload["status"] == "VALIDATING"

    def broken(services: object, upload_id: str) -> None:
        raise RuntimeError("storage unreachable")

    monkeypatch.setattr(uploads, "run_validation", broken)
    monkeypatch.setattr(tasks, "services", lambda: api.services)
    with pytest.raises(Retry):
        tasks.validate_upload.apply(args=[upload["id"]], throw=True)
    still = api.get(f"/api/v1/uploads/{upload['id']}", customer).json()
    assert still["status"] == "VALIDATING"

    # Last attempt: give up and tell the customer to try again.
    monkeypatch.setattr(tasks, "VALIDATION_ATTEMPTS", 0)
    with pytest.raises(RuntimeError):
        tasks.validate_upload.apply(args=[upload["id"]], throw=True)
    result = api.get(f"/api/v1/uploads/{upload['id']}", customer).json()
    assert result["status"] == "REJECTED"
    assert result["rejection_code"] == "SCAN_FAILED"
    # Running it again on a finished upload changes nothing.
    uploads.mark_check_failed(api.services, upload["id"])
