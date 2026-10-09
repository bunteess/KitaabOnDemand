import uuid
from datetime import datetime

from sqlalchemy import BigInteger, ForeignKey, Index, String, text
from sqlalchemy.orm import Mapped, mapped_column

from kitaab.db import Base
from kitaab.domain.enums import LedgerEntryType, PayoutBatchStatus
from kitaab.models.base import default_now, enum_column, required_timestamp, timestamp, uuid_pk

# Each of these entry types happens at most once per order.
_ONCE_PER_ORDER = "('COD_COLLECTED', 'COD_REMITTED', 'VENDOR_COST_ACCRUED', 'VENDOR_PAYOUT')"


class LedgerEntry(Base):
    """Append-only money movements. A trigger rejects UPDATE and DELETE (D-028).

    Amounts are always positive; the entry type says which way money moved.
    """

    __tablename__ = "ledger_entries"
    __table_args__ = (
        Index(
            "uq_ledger_once_per_order",
            "order_id",
            "entry_type",
            unique=True,
            postgresql_where=text(f"entry_type IN {_ONCE_PER_ORDER}"),
        ),
        Index(
            "uq_ledger_revenue_payment",
            "payment_id",
            unique=True,
            postgresql_where=text("entry_type = 'REVENUE'"),
        ),
        Index(
            "uq_ledger_refund",
            "refund_id",
            unique=True,
            postgresql_where=text("entry_type = 'REFUND'"),
        ),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    entry_type: Mapped[LedgerEntryType] = mapped_column(enum_column(LedgerEntryType), index=True)
    amount_paisa: Mapped[int] = mapped_column(BigInteger)
    order_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("orders.id"), index=True)
    payment_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("payments.id"))
    refund_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("refunds.id"))
    payment_method: Mapped[str | None] = mapped_column(String(20))
    courier_code: Mapped[str | None] = mapped_column(String(30))
    vendor_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("vendors.id"), index=True)
    payout_batch_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("payout_batches.id"))
    reference: Mapped[str | None] = mapped_column(String(100))
    occurred_at: Mapped[datetime] = required_timestamp()
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = default_now()


class PayoutBatch(Base):
    __tablename__ = "payout_batches"

    id: Mapped[uuid.UUID] = uuid_pk()
    vendor_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("vendors.id"), index=True)
    status: Mapped[PayoutBatchStatus] = mapped_column(enum_column(PayoutBatchStatus))
    total_paisa: Mapped[int] = mapped_column(BigInteger)
    reference: Mapped[str | None] = mapped_column(String(100))
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = default_now()
    paid_at: Mapped[datetime | None] = timestamp()


class PayoutBatchItem(Base):
    __tablename__ = "payout_batch_items"

    batch_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("payout_batches.id", ondelete="CASCADE"), primary_key=True
    )
    order_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("orders.id"), primary_key=True, unique=True
    )
    amount_paisa: Mapped[int] = mapped_column(BigInteger)
