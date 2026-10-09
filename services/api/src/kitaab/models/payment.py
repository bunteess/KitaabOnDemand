import uuid
from datetime import datetime

from sqlalchemy import BigInteger, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from kitaab.db import Base
from kitaab.domain.enums import PaymentMethod, PaymentStatus, RefundStatus
from kitaab.models.base import default_now, enum_column, timestamp, uuid_pk


class Payment(Base):
    """One attempt to pay for an order. COD payments are PAID once the cash is remitted."""

    __tablename__ = "payments"

    id: Mapped[uuid.UUID] = uuid_pk()
    order_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("orders.id", ondelete="CASCADE"), index=True
    )
    method: Mapped[PaymentMethod] = mapped_column(enum_column(PaymentMethod))
    provider: Mapped[str] = mapped_column(String(30))
    amount_paisa: Mapped[int] = mapped_column(BigInteger)
    status: Mapped[PaymentStatus] = mapped_column(enum_column(PaymentStatus), index=True)
    provider_ref: Mapped[str | None] = mapped_column(String(120), unique=True)
    checkout_url: Mapped[str | None] = mapped_column(String(1000))
    failure_reason: Mapped[str | None] = mapped_column(String(300))
    created_at: Mapped[datetime] = default_now()
    paid_at: Mapped[datetime | None] = timestamp()
    failed_at: Mapped[datetime | None] = timestamp()


class Refund(Base):
    __tablename__ = "refunds"

    id: Mapped[uuid.UUID] = uuid_pk()
    order_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("orders.id", ondelete="CASCADE"), index=True
    )
    payment_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("payments.id"))
    amount_paisa: Mapped[int] = mapped_column(BigInteger)
    status: Mapped[RefundStatus] = mapped_column(enum_column(RefundStatus), index=True)
    reason: Mapped[str] = mapped_column(String(500))
    reference: Mapped[str | None] = mapped_column(String(100))
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    processed_by_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = default_now()
    processed_at: Mapped[datetime | None] = timestamp()


class WebhookEvent(Base):
    """Idempotency keys for incoming payment and courier webhooks."""

    __tablename__ = "webhook_events"
    __table_args__ = (UniqueConstraint("provider", "event_key"),)

    id: Mapped[uuid.UUID] = uuid_pk()
    provider: Mapped[str] = mapped_column(String(30))
    event_key: Mapped[str] = mapped_column(String(200))
    received_at: Mapped[datetime] = default_now()
