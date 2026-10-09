"""Shared column helpers."""

import uuid
from datetime import datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import DateTime, Enum, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from kitaab.clock import utcnow


def enum_column(enum: type[StrEnum]) -> Any:
    """Store enums as plain strings. Python validates values; adding a value
    needs no database migration."""
    return Enum(enum, native_enum=False, create_constraint=False, length=32, validate_strings=True)


def uuid_pk() -> Mapped[uuid.UUID]:
    return mapped_column(Uuid, primary_key=True, default=uuid.uuid4)


def default_now() -> Mapped[datetime]:
    return mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


def auto_updated() -> Mapped[datetime]:
    return mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)


def timestamp() -> Mapped[datetime | None]:
    return mapped_column(DateTime(timezone=True), nullable=True)


def required_timestamp() -> Mapped[datetime]:
    return mapped_column(DateTime(timezone=True), nullable=False)
