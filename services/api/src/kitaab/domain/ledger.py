"""The money ledger (docs/ARCHITECTURE.md, brief section 3.9).

`ledger_entries` is append-only: every function here only inserts. Amounts are
positive; the entry type says which way money moved.

- REVENUE: a digital payment is paid, or the courier collects COD (D-017).
- COD_COLLECTED / COD_REMITTED: cash the courier holds, then sends to us.
- VENDOR_COST_ACCRUED / VENDOR_PAYOUT: what we owe a vendor, then pay them.
- REFUND: money returned to a customer.
"""

import datetime as dt
import uuid
from collections import defaultdict
from dataclasses import dataclass

from sqlalchemy import and_, func, select
from sqlalchemy.orm import aliased

from kitaab.domain.context import Ctx
from kitaab.domain.enums import LedgerEntryType as L
from kitaab.domain.enums import PaymentMethod, PaymentStatus, PayoutBatchStatus
from kitaab.models import LedgerEntry, Order, Payment, PayoutBatch, PayoutBatchItem, Refund, Vendor
from kitaab.problems import conflict, invalid, not_found

PKT = "Asia/Karachi"


def _add(ctx: Ctx, entry_type: L, amount: int, **fields: object) -> LedgerEntry:
    if amount < 0:
        raise ValueError("ledger amounts are positive")
    entry = LedgerEntry(
        entry_type=entry_type,
        amount_paisa=amount,
        occurred_at=ctx.now,
        created_by_id=ctx.user.id if ctx.user else None,
        created_at=ctx.now,
        **fields,
    )
    ctx.session.add(entry)
    ctx.session.flush()
    return entry


def _exists(ctx: Ctx, entry_type: L, **filters: object) -> bool:
    clauses = [LedgerEntry.entry_type == entry_type] + [
        getattr(LedgerEntry, k) == v for k, v in filters.items()
    ]
    count = ctx.session.scalar(select(func.count()).select_from(LedgerEntry).where(*clauses))
    return (count or 0) > 0


def record_revenue(ctx: Ctx, order: Order, payment: Payment) -> None:
    if not _exists(ctx, L.REVENUE, payment_id=payment.id):
        _add(
            ctx,
            L.REVENUE,
            payment.amount_paisa,
            order_id=order.id,
            payment_id=payment.id,
            payment_method=payment.method.value,
            courier_code=order.courier_code,
        )


def record_cod_collected(ctx: Ctx, order: Order, payment: Payment) -> None:
    """On delivery: the courier now holds the cash. Also recognises the revenue."""
    if not _exists(ctx, L.COD_COLLECTED, order_id=order.id):
        _add(
            ctx,
            L.COD_COLLECTED,
            payment.amount_paisa,
            order_id=order.id,
            payment_id=payment.id,
            payment_method=PaymentMethod.COD.value,
            courier_code=order.courier_code,
        )
    record_revenue(ctx, order, payment)


def accrue_vendor_cost(ctx: Ctx, order: Order) -> None:
    if order.vendor_id is None or not order.vendor_cost_paisa:
        return
    if not _exists(ctx, L.VENDOR_COST_ACCRUED, order_id=order.id):
        _add(
            ctx,
            L.VENDOR_COST_ACCRUED,
            order.vendor_cost_paisa,
            order_id=order.id,
            vendor_id=order.vendor_id,
        )


def record_refund(ctx: Ctx, refund: Refund, order: Order) -> None:
    if not _exists(ctx, L.REFUND, refund_id=refund.id):
        _add(
            ctx,
            L.REFUND,
            refund.amount_paisa,
            order_id=order.id,
            refund_id=refund.id,
            payment_id=refund.payment_id,
            payment_method=order.payment_method.value if order.payment_method else None,
            reference=refund.reference,
        )


@dataclass(frozen=True)
class Remittance:
    courier_code: str
    orders: list[Order]
    total_paisa: int
    reference: str


def record_cod_remittance(
    ctx: Ctx, courier_code: str, order_ids: list[uuid.UUID], reference: str
) -> Remittance:
    """The courier sent us the cash for these orders. Each order's COD payment becomes PAID."""
    collected = aliased(LedgerEntry)
    rows = ctx.session.execute(
        select(Order, collected.amount_paisa)
        .join(
            collected, and_(collected.order_id == Order.id, collected.entry_type == L.COD_COLLECTED)
        )
        .where(Order.id.in_(order_ids))
        .with_for_update(of=Order)
    ).all()
    if len(rows) != len(set(order_ids)):
        raise invalid("cod-not-collected", "Some orders have no COD collected by a courier")
    remitted: list[Order] = []
    total = 0
    for order, amount in rows:
        if order.courier_code != courier_code:
            raise invalid(
                "courier-mismatch", f"Order {order.code} was not shipped with this courier"
            )
        if _exists(ctx, L.COD_REMITTED, order_id=order.id):
            raise conflict("already-remitted", f"Order {order.code} is already marked remitted")
        _add(
            ctx,
            L.COD_REMITTED,
            amount,
            order_id=order.id,
            payment_method=PaymentMethod.COD.value,
            courier_code=courier_code,
            reference=reference,
        )
        payment = ctx.session.scalar(
            select(Payment).where(
                Payment.order_id == order.id,
                Payment.method == PaymentMethod.COD,
                Payment.status == PaymentStatus.PENDING,
            )
        )
        if payment is not None:
            payment.status = PaymentStatus.PAID
            payment.paid_at = ctx.now
        order.payment_status = PaymentStatus.PAID
        remitted.append(order)
        total += amount
    return Remittance(courier_code, remitted, total, reference)


def create_payout_batch(ctx: Ctx, vendor_id: uuid.UUID) -> PayoutBatch:
    """Batch every accrued vendor cost that is not yet in a batch."""
    vendor = ctx.session.get(Vendor, vendor_id)
    if vendor is None:
        raise not_found("Vendor")
    unbatched = ctx.session.execute(
        select(LedgerEntry.order_id, LedgerEntry.amount_paisa)
        .outerjoin(PayoutBatchItem, PayoutBatchItem.order_id == LedgerEntry.order_id)
        .where(
            LedgerEntry.entry_type == L.VENDOR_COST_ACCRUED,
            LedgerEntry.vendor_id == vendor_id,
            PayoutBatchItem.order_id.is_(None),
        )
    ).all()
    if not unbatched:
        raise conflict("nothing-to-pay", "This vendor has no unbatched costs")
    batch = PayoutBatch(
        vendor_id=vendor_id,
        status=PayoutBatchStatus.OPEN,
        total_paisa=sum(amount for _, amount in unbatched),
        created_by_id=ctx.user.id if ctx.user else None,
        created_at=ctx.now,
    )
    ctx.session.add(batch)
    ctx.session.flush()
    for order_id, amount in unbatched:
        ctx.session.add(PayoutBatchItem(batch_id=batch.id, order_id=order_id, amount_paisa=amount))
    ctx.session.flush()
    return batch


def mark_batch_paid(ctx: Ctx, batch_id: uuid.UUID, reference: str) -> PayoutBatch:
    batch = ctx.session.get(PayoutBatch, batch_id, with_for_update=True)
    if batch is None:
        raise not_found("Payout batch")
    if batch.status == PayoutBatchStatus.PAID:
        raise conflict("already-paid", "This batch is already paid")
    items = ctx.session.scalars(
        select(PayoutBatchItem).where(PayoutBatchItem.batch_id == batch.id)
    ).all()
    for item in items:
        _add(
            ctx,
            L.VENDOR_PAYOUT,
            item.amount_paisa,
            order_id=item.order_id,
            vendor_id=batch.vendor_id,
            payout_batch_id=batch.id,
            reference=reference,
        )
    batch.status = PayoutBatchStatus.PAID
    batch.reference = reference
    batch.paid_at = ctx.now
    return batch


# -- reports -------------------------------------------------------------------------


@dataclass(frozen=True)
class RevenueRow:
    date: dt.date
    payment_method: PaymentMethod
    orders: int
    gross_paisa: int
    refunds_paisa: int

    @property
    def net_paisa(self) -> int:
        return self.gross_paisa - self.refunds_paisa


def daily_revenue(ctx: Ctx, from_date: dt.date, to_date: dt.date) -> list[RevenueRow]:
    """Revenue and refunds by Pakistan calendar day and payment method."""
    if to_date < from_date:
        raise invalid("invalid-range", "The end date is before the start date")
    if (to_date - from_date).days > 366:
        raise invalid("invalid-range", "Choose a range of at most one year")
    day = func.date(func.timezone(PKT, LedgerEntry.occurred_at)).label("day")
    rows = ctx.session.execute(
        select(
            day,
            LedgerEntry.payment_method,
            LedgerEntry.entry_type,
            func.sum(LedgerEntry.amount_paisa),
            func.count(func.distinct(LedgerEntry.order_id)),
        )
        .where(LedgerEntry.entry_type.in_([L.REVENUE, L.REFUND]), day >= from_date, day <= to_date)
        .group_by(day, LedgerEntry.payment_method, LedgerEntry.entry_type)
    ).all()
    grouped: dict[tuple[dt.date, str], dict[str, int]] = defaultdict(
        lambda: {"gross": 0, "refunds": 0, "orders": 0}
    )
    for row_day, method, entry_type, amount, orders in rows:
        bucket = grouped[(row_day, method or PaymentMethod.COD.value)]
        if entry_type == L.REVENUE:
            bucket["gross"] += int(amount)
            bucket["orders"] += int(orders)
        else:
            bucket["refunds"] += int(amount)
    return [
        RevenueRow(day_, PaymentMethod(method), v["orders"], v["gross"], v["refunds"])
        for (day_, method), v in sorted(grouped.items())
    ]


@dataclass(frozen=True)
class CodPending:
    order_id: uuid.UUID
    order_code: str
    courier_code: str
    cn_number: str | None
    amount_paisa: int
    delivered_at: dt.datetime


def cod_pending(ctx: Ctx) -> list[CodPending]:
    remitted = aliased(LedgerEntry)
    rows = ctx.session.execute(
        select(LedgerEntry, Order)
        .join(Order, Order.id == LedgerEntry.order_id)
        .outerjoin(
            remitted,
            and_(remitted.order_id == LedgerEntry.order_id, remitted.entry_type == L.COD_REMITTED),
        )
        .where(LedgerEntry.entry_type == L.COD_COLLECTED, remitted.id.is_(None))
        .order_by(LedgerEntry.courier_code, LedgerEntry.occurred_at)
    ).all()
    return [
        CodPending(
            order.id,
            order.code,
            entry.courier_code or "",
            order.cn_number,
            entry.amount_paisa,
            order.delivered_at or entry.occurred_at,
        )
        for entry, order in rows
    ]


@dataclass(frozen=True)
class VendorBalance:
    vendor_id: uuid.UUID
    vendor_name: str
    accrued_paisa: int
    paid_paisa: int
    in_open_batches_paisa: int

    @property
    def owed_paisa(self) -> int:
        return self.accrued_paisa - self.paid_paisa


def vendor_balances(ctx: Ctx) -> list[VendorBalance]:
    sums = {
        (vendor_id, entry_type): int(total)
        for vendor_id, entry_type, total in ctx.session.execute(
            select(
                LedgerEntry.vendor_id, LedgerEntry.entry_type, func.sum(LedgerEntry.amount_paisa)
            )
            .where(LedgerEntry.entry_type.in_([L.VENDOR_COST_ACCRUED, L.VENDOR_PAYOUT]))
            .group_by(LedgerEntry.vendor_id, LedgerEntry.entry_type)
        ).all()
    }
    open_batches = {
        vendor_id: int(total)
        for vendor_id, total in ctx.session.execute(
            select(PayoutBatch.vendor_id, func.sum(PayoutBatch.total_paisa))
            .where(PayoutBatch.status == PayoutBatchStatus.OPEN)
            .group_by(PayoutBatch.vendor_id)
        ).all()
    }
    vendors = ctx.session.scalars(select(Vendor).order_by(Vendor.name)).all()
    return [
        VendorBalance(
            v.id,
            v.name,
            sums.get((v.id, L.VENDOR_COST_ACCRUED), 0),
            sums.get((v.id, L.VENDOR_PAYOUT), 0),
            open_batches.get(v.id, 0),
        )
        for v in vendors
        if (v.id, L.VENDOR_COST_ACCRUED) in sums or v.is_active
    ]
