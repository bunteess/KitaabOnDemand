import csv
import datetime as dt
import io
import uuid
from collections import defaultdict
from collections.abc import Iterable

from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import Response
from sqlalchemy import select

from kitaab.domain import audit, ledger
from kitaab.domain.context import Ctx
from kitaab.domain.orders import service as orders
from kitaab.models import Order, PayoutBatch, PayoutBatchItem, Vendor
from kitaab.problems import CSV_RESPONSE, not_found
from kitaab.schemas.finance import (
    CodPendingGroup,
    CodPendingOrder,
    CodRemittanceCreate,
    CodRemittanceResult,
    DailyRevenueReport,
    DailyRevenueRow,
    PayoutBatchCreate,
    PayoutBatchOut,
    PayoutBatchPay,
    VendorPayoutRow,
)
from kitaab.schemas.finance import (
    PayoutBatchItem as PayoutBatchItemOut,
)
from kitaab.security.deps import admin_ctx

router = APIRouter(prefix="/admin/finance", tags=["admin: finance"])


def _csv(filename: str, header: list[str], rows: Iterable[Iterable[object]]) -> Response:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(header)
    writer.writerows(rows)
    return Response(
        buffer.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def _rupees(paisa: int) -> str:
    return f"{paisa / 100:.2f}"


def _revenue(ctx: Ctx, from_date: dt.date, to_date: dt.date) -> DailyRevenueReport:
    rows = ledger.daily_revenue(ctx, from_date, to_date)
    return DailyRevenueReport(
        from_date=from_date,
        to_date=to_date,
        rows=[
            DailyRevenueRow(
                date=r.date,
                payment_method=r.payment_method,
                orders=r.orders,
                gross_paisa=r.gross_paisa,
                refunds_paisa=r.refunds_paisa,
                net_paisa=r.net_paisa,
            )
            for r in rows
        ],
        total_gross_paisa=sum(r.gross_paisa for r in rows),
        total_refunds_paisa=sum(r.refunds_paisa for r in rows),
        total_net_paisa=sum(r.net_paisa for r in rows),
    )


@router.get("/daily-revenue")
def admin_daily_revenue(
    from_date: dt.date, to_date: dt.date, ctx: Ctx = Depends(admin_ctx)
) -> DailyRevenueReport:
    """Revenue by Pakistan calendar day and payment method."""
    return _revenue(ctx, from_date, to_date)


@router.get("/daily-revenue.csv", response_class=Response, responses=CSV_RESPONSE)
def admin_daily_revenue_csv(
    from_date: dt.date, to_date: dt.date, ctx: Ctx = Depends(admin_ctx)
) -> Response:
    report = _revenue(ctx, from_date, to_date)
    return _csv(
        f"revenue-{from_date}-{to_date}.csv",
        ["date", "payment_method", "orders", "gross_pkr", "refunds_pkr", "net_pkr"],
        (
            [
                r.date,
                r.payment_method.value,
                r.orders,
                _rupees(r.gross_paisa),
                _rupees(r.refunds_paisa),
                _rupees(r.net_paisa),
            ]
            for r in report.rows
        ),
    )


def _cod_groups(ctx: Ctx) -> list[CodPendingGroup]:
    grouped: dict[str, list[ledger.CodPending]] = defaultdict(list)
    for item in ledger.cod_pending(ctx):
        grouped[item.courier_code].append(item)
    return [
        CodPendingGroup(
            courier_code=code,
            courier_name=ctx.services.couriers.name_of(code),
            total_paisa=sum(i.amount_paisa for i in items),
            orders=[
                CodPendingOrder(
                    order_id=i.order_id,
                    order_code=i.order_code,
                    cn_number=i.cn_number,
                    amount_paisa=i.amount_paisa,
                    delivered_at=i.delivered_at,
                )
                for i in items
            ],
        )
        for code, items in sorted(grouped.items())
    ]


@router.get("/cod-pending")
def admin_cod_pending(ctx: Ctx = Depends(admin_ctx)) -> list[CodPendingGroup]:
    """Cash collected by couriers and not yet remitted to us, grouped by courier."""
    return _cod_groups(ctx)


@router.get("/cod-pending.csv", response_class=Response, responses=CSV_RESPONSE)
def admin_cod_pending_csv(ctx: Ctx = Depends(admin_ctx)) -> Response:
    return _csv(
        "cod-pending.csv",
        ["courier", "order", "cn", "amount_pkr", "delivered_at"],
        (
            [
                g.courier_code,
                o.order_code,
                o.cn_number or "",
                _rupees(o.amount_paisa),
                o.delivered_at.isoformat(),
            ]
            for g in _cod_groups(ctx)
            for o in g.orders
        ),
    )


@router.post("/cod-remittances", status_code=status.HTTP_201_CREATED)
def admin_record_cod_remittance(
    body: CodRemittanceCreate, ctx: Ctx = Depends(admin_ctx)
) -> CodRemittanceResult:
    """Mark cash for these orders as remitted. Completes the orders."""
    remittance = ledger.record_cod_remittance(
        ctx, body.courier_code, body.order_ids, body.reference
    )
    for order in remittance.orders:
        orders.try_complete(ctx, order)
    audit.record(
        ctx,
        "cod.remitted",
        "courier",
        body.courier_code,
        orders=len(remittance.orders),
        total_paisa=remittance.total_paisa,
        reference=body.reference,
    )
    ctx.session.commit()
    return CodRemittanceResult(
        courier_code=body.courier_code,
        orders=len(remittance.orders),
        total_paisa=remittance.total_paisa,
        reference=body.reference,
    )


@router.get("/vendor-payouts")
def admin_vendor_payouts(ctx: Ctx = Depends(admin_ctx)) -> list[VendorPayoutRow]:
    return [
        VendorPayoutRow(
            vendor_id=b.vendor_id,
            vendor_name=b.vendor_name,
            accrued_paisa=b.accrued_paisa,
            paid_paisa=b.paid_paisa,
            in_open_batches_paisa=b.in_open_batches_paisa,
            owed_paisa=b.owed_paisa,
        )
        for b in ledger.vendor_balances(ctx)
    ]


@router.get("/vendor-payouts.csv", response_class=Response, responses=CSV_RESPONSE)
def admin_vendor_payouts_csv(ctx: Ctx = Depends(admin_ctx)) -> Response:
    return _csv(
        "vendor-payouts.csv",
        ["vendor", "accrued_pkr", "paid_pkr", "in_open_batches_pkr", "owed_pkr"],
        (
            [
                b.vendor_name,
                _rupees(b.accrued_paisa),
                _rupees(b.paid_paisa),
                _rupees(b.in_open_batches_paisa),
                _rupees(b.owed_paisa),
            ]
            for b in ledger.vendor_balances(ctx)
        ),
    )


def _batch_out(ctx: Ctx, batch: PayoutBatch) -> PayoutBatchOut:
    vendor = ctx.session.get(Vendor, batch.vendor_id)
    items = ctx.session.execute(
        select(PayoutBatchItem, Order.code)
        .join(Order, Order.id == PayoutBatchItem.order_id)
        .where(PayoutBatchItem.batch_id == batch.id)
        .order_by(Order.code)
    ).all()
    return PayoutBatchOut(
        id=batch.id,
        vendor_id=batch.vendor_id,
        vendor_name=vendor.name if vendor else "",
        status=batch.status,
        total_paisa=batch.total_paisa,
        reference=batch.reference,
        items=[
            PayoutBatchItemOut(order_id=i.order_id, order_code=code, amount_paisa=i.amount_paisa)
            for i, code in items
        ],
        created_at=batch.created_at,
        paid_at=batch.paid_at,
    )


@router.get("/payout-batches")
def admin_list_payout_batches(
    vendor_id: uuid.UUID | None = None, page: int = Query(1, ge=1), ctx: Ctx = Depends(admin_ctx)
) -> list[PayoutBatchOut]:
    query = select(PayoutBatch)
    if vendor_id is not None:
        query = query.where(PayoutBatch.vendor_id == vendor_id)
    rows = ctx.session.scalars(
        query.order_by(PayoutBatch.created_at.desc()).offset((page - 1) * 50).limit(50)
    )
    return [_batch_out(ctx, b) for b in rows]


@router.post("/payout-batches", status_code=status.HTTP_201_CREATED)
def admin_create_payout_batch(
    body: PayoutBatchCreate, ctx: Ctx = Depends(admin_ctx)
) -> PayoutBatchOut:
    """Group every accrued, unbatched vendor cost into a batch."""
    batch = ledger.create_payout_batch(ctx, body.vendor_id)
    audit.record(
        ctx, "payout.batch_created", "payout_batch", batch.id, total_paisa=batch.total_paisa
    )
    ctx.session.commit()
    return _batch_out(ctx, batch)


@router.post("/payout-batches/{batch_id}/mark-paid")
def admin_mark_payout_paid(
    batch_id: uuid.UUID, body: PayoutBatchPay, ctx: Ctx = Depends(admin_ctx)
) -> PayoutBatchOut:
    batch = ledger.mark_batch_paid(ctx, batch_id, body.reference)
    audit.record(
        ctx,
        "payout.paid",
        "payout_batch",
        batch.id,
        total_paisa=batch.total_paisa,
        reference=body.reference,
    )
    ctx.session.commit()
    return _batch_out(ctx, batch)


@router.get("/payout-batches/{batch_id}.csv", response_class=Response, responses=CSV_RESPONSE)
def admin_payout_batch_csv(batch_id: uuid.UUID, ctx: Ctx = Depends(admin_ctx)) -> Response:
    batch = ctx.session.get(PayoutBatch, batch_id)
    if batch is None:
        raise not_found("Payout batch")
    out = _batch_out(ctx, batch)
    return _csv(
        f"payout-{batch.id}.csv",
        ["vendor", "order", "amount_pkr", "status", "reference"],
        (
            [
                out.vendor_name,
                i.order_code,
                _rupees(i.amount_paisa),
                out.status.value,
                out.reference or "",
            ]
            for i in out.items
        ),
    )
