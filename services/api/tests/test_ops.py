"""CLI, OpenAPI export and worker wiring."""

from pathlib import Path

import pytest
from sqlalchemy import inspect

from kitaab import cli, openapi_export
from kitaab.db import get_engine
from kitaab.workers.celery_app import ping


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
