"""Test configuration.

Integration tests use the Postgres, Redis and MinIO started by `make deps-up`.
Environment variables are set before any kitaab module reads settings.

The `api` fixture gives a running app with test services: a frozen clock,
in-memory SMS, push, payment and courier fakes, MinIO storage and an inline
job queue, so background jobs run as soon as the request's transaction commits.
"""

import os

os.environ.setdefault("ENVIRONMENT", "test")
os.environ["DATABASE_URL"] = os.environ.get(
    "TEST_DATABASE_URL", "postgresql+psycopg://kitaab:kitaab@localhost:5432/kitaab_test"
)
os.environ["REDIS_URL"] = os.environ.get("TEST_REDIS_URL", "redis://localhost:6379/15")
os.environ["S3_ENDPOINT_URL"] = os.environ.get("TEST_S3_ENDPOINT_URL", "http://localhost:9000")
os.environ["S3_PUBLIC_ENDPOINT_URL"] = os.environ["S3_ENDPOINT_URL"]
os.environ["S3_BUCKET"] = os.environ.get("TEST_S3_BUCKET", "kitaab-test")
# Always the local MinIO credentials: tests must never reach real AWS.
os.environ["AWS_ACCESS_KEY_ID"] = os.environ.get("TEST_AWS_ACCESS_KEY_ID", "kitaab-minio")
os.environ["AWS_SECRET_ACCESS_KEY"] = os.environ.get(
    "TEST_AWS_SECRET_ACCESS_KEY", "kitaab-minio-secret"
)
os.environ["DEV_TOOLS_ENABLED"] = "true"
os.environ["PAYMENT_PROVIDERS"] = "mock,easypaisa"
os.environ["COURIER_PROVIDERS"] = "mock,trax"
os.environ["PUBLIC_BASE_URL"] = "http://testserver"

import logging
from collections.abc import Iterator

import pytest
import redis
from alembic import command
from sqlalchemy import Engine, text

from kitaab import clock as clock_module
from kitaab.cli import alembic_config
from kitaab.clock import FrozenClock, SystemClock
from kitaab.config import Settings
from kitaab.container import Services
from kitaab.db import Base, get_engine
from kitaab.domain.context import Ctx
from kitaab.providers.storage import S3ObjectStore
from support import START, Api, build_test_services


@pytest.fixture(scope="session")
def database() -> Engine:
    """The test database, rebuilt from empty with Alembic once per run."""
    engine = get_engine()
    with engine.begin() as connection:
        connection.execute(text("DROP SCHEMA IF EXISTS public CASCADE"))
        connection.execute(text("CREATE SCHEMA public"))
    command.upgrade(alembic_config(), "head")
    return engine


@pytest.fixture
def db(database: Engine) -> Engine:
    """An empty database for each test."""
    tables = ", ".join(f'"{t.name}"' for t in Base.metadata.sorted_tables)
    with database.begin() as connection:
        connection.execute(text(f"TRUNCATE {tables} RESTART IDENTITY CASCADE"))
    return database


@pytest.fixture
def redis_client() -> Iterator["redis.Redis"]:
    client: redis.Redis = redis.Redis.from_url(os.environ["REDIS_URL"])
    client.flushdb()
    yield client
    client.close()


@pytest.fixture(scope="session")
def store() -> S3ObjectStore:
    s = S3ObjectStore(Settings())
    s.ensure_bucket()
    return s


@pytest.fixture
def clock() -> Iterator[FrozenClock]:
    frozen = FrozenClock(START)
    clock_module.install(frozen)
    yield frozen
    clock_module.install(SystemClock())


@pytest.fixture
def settings() -> Settings:
    return Settings()


class _CallbackFailures(logging.Handler):
    def __init__(self) -> None:
        super().__init__(logging.ERROR)
        self.failures: list[logging.LogRecord] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.failures.append(record)


@pytest.fixture(autouse=True)
def fail_on_after_commit_errors() -> Iterator[None]:
    """Jobs run in after-commit callbacks, which only log failures. Tests must not."""
    handler = _CallbackFailures()
    logger = logging.getLogger("kitaab.tx")
    logger.addHandler(handler)
    yield
    logger.removeHandler(handler)
    if handler.failures:
        record = handler.failures[0]
        detail = record.exc_text or (
            logging.Formatter().formatException(record.exc_info) if record.exc_info else ""
        )
        pytest.fail(f"an after-commit callback failed:\n{detail}")


@pytest.fixture
def services(
    db: Engine,
    redis_client: "redis.Redis",
    store: S3ObjectStore,
    clock: FrozenClock,
    settings: Settings,
) -> Services:
    return build_test_services(settings, clock, redis_client, store)


@pytest.fixture
def ctx(services: Services) -> Iterator[Ctx]:
    """A database session and services, for calling domain functions directly."""
    context = Ctx(services.session(), services)
    yield context
    context.session.close()


@pytest.fixture
def api(services: Services) -> Iterator[Api]:
    harness = Api(services)
    harness.seed()
    yield harness
    harness.close()
