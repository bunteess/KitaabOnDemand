import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from kitaab.db import Base
from kitaab.models.base import auto_updated, default_now, required_timestamp, uuid_pk


class City(Base):
    __tablename__ = "cities"

    id: Mapped[uuid.UUID] = uuid_pk()
    name: Mapped[str] = mapped_column(String(80), unique=True)
    province: Mapped[str] = mapped_column(String(80))
    zone_code: Mapped[str] = mapped_column(String(20))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = default_now()


class Address(Base):
    __tablename__ = "addresses"

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    label: Mapped[str | None] = mapped_column(String(120))
    recipient_name: Mapped[str] = mapped_column(String(120))
    recipient_phone_e164: Mapped[str] = mapped_column(String(16))
    city_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("cities.id"))
    area: Mapped[str] = mapped_column(String(120))
    street_address: Mapped[str] = mapped_column(String(1000))
    landmark: Mapped[str] = mapped_column(String(120))
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = default_now()
    updated_at: Mapped[datetime] = auto_updated()

    city: Mapped[City] = relationship(lazy="joined")


class PricingConfig(Base):
    """A versioned set of pricing rules. Orders store the version they used."""

    __tablename__ = "pricing_configs"

    id: Mapped[uuid.UUID] = uuid_pk()
    version: Mapped[int] = mapped_column(Integer, unique=True)
    effective_from: Mapped[datetime] = required_timestamp()
    rules: Mapped[dict[str, Any]] = mapped_column(JSONB)
    notes: Mapped[str | None] = mapped_column(Text)
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = default_now()


class AppSetting(Base):
    """Admin-editable settings, such as COD_MAX_ORDER_VALUE."""

    __tablename__ = "app_settings"

    key: Mapped[str] = mapped_column(String(60), primary_key=True)
    value: Mapped[Any] = mapped_column(JSONB)
    updated_by_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    updated_at: Mapped[datetime] = auto_updated()


class Vendor(Base):
    __tablename__ = "vendors"

    id: Mapped[uuid.UUID] = uuid_pk()
    name: Mapped[str] = mapped_column(String(120))
    contact_name: Mapped[str] = mapped_column(String(120))
    contact_phone_e164: Mapped[str] = mapped_column(String(16))
    email: Mapped[str | None] = mapped_column(String(254))
    city_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("cities.id"))
    address: Mapped[str | None] = mapped_column(String(1000))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = default_now()
    updated_at: Mapped[datetime] = auto_updated()
