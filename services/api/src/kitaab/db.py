"""Database engine and sessions."""

from functools import lru_cache

from sqlalchemy import Engine, MetaData, create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from kitaab.config import get_settings

# Stable constraint names so Alembic autogenerate produces predictable migrations.
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


@lru_cache
def get_engine() -> Engine:
    settings = get_settings()
    # Sync endpoints run on a thread pool (THREADPOOL_SIZE). With fewer
    # connections than threads, threads block waiting for a connection while
    # the sessions holding them wait for a thread to close: a deadlock under
    # load (docs/PERF.md). So the pool can always give every thread one.
    return create_engine(
        settings.database_url,
        pool_pre_ping=True,
        pool_size=settings.db_pool_size,
        max_overflow=max(0, settings.threadpool_size - settings.db_pool_size),
        pool_timeout=settings.db_pool_timeout_seconds,
    )


@lru_cache
def get_session_factory() -> sessionmaker[Session]:
    return sessionmaker(bind=get_engine(), expire_on_commit=False)
