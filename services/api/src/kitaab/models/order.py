import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, ForeignKey, Identity, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from kitaab.db import Base
from kitaab.domain.enums import (
    Actor,
    Binding,
    OrderStatus,
    OrderType,
    Paper,
    PaymentMethod,
    PaymentStatus,
    QuoteStatus,
)
from kitaab.models.base import (
    auto_updated,
    default_now,
    enum_column,
    required_timestamp,
    timestamp,
    uuid_pk,
)
from kitaab.models.catalog import Vendor
from kitaab.models.upload import Upload
from kitaab.models.user import User


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[uuid.UUID] = uuid_pk()
    code: Mapped[str] = mapped_column(String(12), unique=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    type: Mapped[OrderType] = mapped_column(enum_column(OrderType), index=True)
    status: Mapped[OrderStatus] = mapped_column(enum_column(OrderStatus), index=True)

    # PRINT
    upload_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("uploads.id"), unique=True)
    # SOURCE book request
    book_title: Mapped[str | None] = mapped_column(String(200))
    book_author: Mapped[str | None] = mapped_column(String(120))
    book_isbn: Mapped[str | None] = mapped_column(String(20))
    book_edition: Mapped[str | None] = mapped_column(String(120))
    book_notes: Mapped[str | None] = mapped_column(Text)
    preferred_paper: Mapped[Paper | None] = mapped_column(enum_column(Paper))
    preferred_binding: Mapped[Binding | None] = mapped_column(enum_column(Binding))

    # Print specification (PRINT at checkout, SOURCE from the accepted quote)
    pages: Mapped[int | None] = mapped_column(Integer)
    paper: Mapped[Paper | None] = mapped_column(enum_column(Paper))
    binding: Mapped[Binding | None] = mapped_column(enum_column(Binding))
    copies: Mapped[int] = mapped_column(Integer, default=1)

    # Price snapshot
    payment_method: Mapped[PaymentMethod | None] = mapped_column(enum_column(PaymentMethod))
    payment_status: Mapped[PaymentStatus | None] = mapped_column(enum_column(PaymentStatus))
    pricing_config_version: Mapped[int | None] = mapped_column(Integer)
    price_breakdown: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    total_paisa: Mapped[int | None] = mapped_column(BigInteger)

    # Shipping snapshot (scrubbed after a deleted account's order finishes)
    ship_recipient_name: Mapped[str | None] = mapped_column(String(120))
    ship_recipient_phone_e164: Mapped[str | None] = mapped_column(String(16))
    ship_city_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("cities.id"))
    ship_city_name: Mapped[str] = mapped_column(String(80))
    ship_zone_code: Mapped[str] = mapped_column(String(20))
    ship_area: Mapped[str | None] = mapped_column(String(120))
    ship_street_address: Mapped[str | None] = mapped_column(String(1000))
    ship_landmark: Mapped[str | None] = mapped_column(String(120))

    # Fulfilment
    vendor_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("vendors.id"), index=True)
    vendor_cost_paisa: Mapped[int | None] = mapped_column(BigInteger)
    assigned_at: Mapped[datetime | None] = timestamp()
    courier_code: Mapped[str | None] = mapped_column(String(30))
    cn_number: Mapped[str | None] = mapped_column(String(60), index=True)
    tracking_url: Mapped[str | None] = mapped_column(String(500))
    courier_status: Mapped[str | None] = mapped_column(String(120))
    dispatched_at: Mapped[datetime | None] = timestamp()
    delivered_at: Mapped[datetime | None] = timestamp()
    completed_at: Mapped[datetime | None] = timestamp()
    terminal_at: Mapped[datetime | None] = timestamp()
    exit_reason: Mapped[str | None] = mapped_column(String(500))
    pii_scrubbed_at: Mapped[datetime | None] = timestamp()

    created_at: Mapped[datetime] = default_now()
    updated_at: Mapped[datetime] = auto_updated()

    user: Mapped[User] = relationship(lazy="joined")
    upload: Mapped[Upload | None] = relationship(lazy="joined")
    vendor: Mapped[Vendor | None] = relationship(lazy="joined")


class OrderStatusHistory(Base):
    __tablename__ = "order_status_history"

    id: Mapped[uuid.UUID] = uuid_pk()
    order_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("orders.id", ondelete="CASCADE"), index=True
    )
    from_status: Mapped[OrderStatus | None] = mapped_column(enum_column(OrderStatus))
    to_status: Mapped[OrderStatus] = mapped_column(enum_column(OrderStatus))
    actor: Mapped[Actor] = mapped_column(enum_column(Actor))
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    reason: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = default_now()
    # Insertion order: several changes can share a timestamp (delivered, then
    # completed, in one transaction).
    seq: Mapped[int] = mapped_column(BigInteger, Identity(always=True))


class Quote(Base):
    __tablename__ = "quotes"

    id: Mapped[uuid.UUID] = uuid_pk()
    order_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("orders.id", ondelete="CASCADE"), index=True
    )
    status: Mapped[QuoteStatus] = mapped_column(enum_column(QuoteStatus), index=True)
    pages: Mapped[int] = mapped_column(Integer)
    paper: Mapped[Paper] = mapped_column(enum_column(Paper))
    binding: Mapped[Binding] = mapped_column(enum_column(Binding))
    copies: Mapped[int] = mapped_column(Integer)
    sourcing_cost_paisa: Mapped[int] = mapped_column(BigInteger)
    calculated_goods_paisa: Mapped[int] = mapped_column(BigInteger)
    goods_paisa: Mapped[int] = mapped_column(BigInteger)
    override_reason: Mapped[str | None] = mapped_column(String(500))
    pricing_config_version: Mapped[int] = mapped_column(Integer)
    breakdown: Mapped[dict[str, Any]] = mapped_column(JSONB)
    valid_until: Mapped[datetime] = required_timestamp()
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = default_now()
    responded_at: Mapped[datetime | None] = timestamp()
