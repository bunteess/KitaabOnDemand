"""Migrations: upgrade from an empty database (the `database` fixture does
this for every run), downgrade back to empty, and no drift between the models
and the migrations."""

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import Engine, inspect, text

from kitaab import models  # noqa: F401  (registers every table)
from kitaab.cli import alembic_config
from kitaab.db import Base

pytestmark = pytest.mark.integration


def test_models_match_the_migrations(database: Engine) -> None:
    with database.connect() as connection:
        diff = compare_metadata(
            MigrationContext.configure(connection, opts={"compare_type": True}), Base.metadata
        )
    assert diff == [], "models and migrations differ: run 'alembic revision --autogenerate'"


def test_every_table_exists(database: Engine) -> None:
    tables = set(inspect(database).get_table_names())
    assert {t.name for t in Base.metadata.sorted_tables} <= tables
    assert "alembic_version" in tables


def test_downgrade_to_empty_and_upgrade_again(database: Engine) -> None:
    config = alembic_config()
    command.downgrade(config, "base")
    with database.connect() as connection:
        left = set(inspect(connection).get_table_names()) - {"alembic_version"}
        functions = connection.execute(
            text("SELECT count(*) FROM pg_proc WHERE proname = 'ledger_entries_append_only'")
        ).scalar()
    assert left == set()
    assert functions == 0
    command.upgrade(config, "head")
    assert {t.name for t in Base.metadata.sorted_tables} <= set(inspect(database).get_table_names())
