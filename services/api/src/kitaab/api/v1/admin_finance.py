import datetime as dt
import uuid

from fastapi import APIRouter, Query, status
from fastapi.responses import Response

from kitaab.problems import CSV_RESPONSE, not_implemented
from kitaab.schemas.finance import (
    CodPendingGroup,
    CodRemittanceCreate,
    CodRemittanceResult,
    DailyRevenueReport,
    PayoutBatchCreate,
    PayoutBatchOut,
    PayoutBatchPay,
    VendorPayoutRow,
)

router = APIRouter(prefix="/admin/finance", tags=["admin: finance"])


@router.get("/daily-revenue")
def admin_daily_revenue(from_date: dt.date, to_date: dt.date) -> DailyRevenueReport:
    """Revenue by Pakistan calendar day and payment method."""
    raise not_implemented()


@router.get("/daily-revenue.csv", response_class=Response, responses=CSV_RESPONSE)
def admin_daily_revenue_csv(from_date: dt.date, to_date: dt.date) -> Response:
    raise not_implemented()


@router.get("/cod-pending")
def admin_cod_pending() -> list[CodPendingGroup]:
    """Cash collected by couriers and not yet remitted to us, grouped by courier."""
    raise not_implemented()


@router.get("/cod-pending.csv", response_class=Response, responses=CSV_RESPONSE)
def admin_cod_pending_csv() -> Response:
    raise not_implemented()


@router.post("/cod-remittances", status_code=status.HTTP_201_CREATED)
def admin_record_cod_remittance(body: CodRemittanceCreate) -> CodRemittanceResult:
    """Mark cash for these orders as remitted. Completes the orders."""
    raise not_implemented()


@router.get("/vendor-payouts")
def admin_vendor_payouts() -> list[VendorPayoutRow]:
    raise not_implemented()


@router.get("/vendor-payouts.csv", response_class=Response, responses=CSV_RESPONSE)
def admin_vendor_payouts_csv() -> Response:
    raise not_implemented()


@router.get("/payout-batches")
def admin_list_payout_batches(
    vendor_id: uuid.UUID | None = None, page: int = Query(1, ge=1)
) -> list[PayoutBatchOut]:
    raise not_implemented()


@router.post("/payout-batches", status_code=status.HTTP_201_CREATED)
def admin_create_payout_batch(body: PayoutBatchCreate) -> PayoutBatchOut:
    """Group every accrued, unbatched vendor cost into a batch."""
    raise not_implemented()


@router.post("/payout-batches/{batch_id}/mark-paid")
def admin_mark_payout_paid(batch_id: uuid.UUID, body: PayoutBatchPay) -> PayoutBatchOut:
    raise not_implemented()


@router.get("/payout-batches/{batch_id}.csv", response_class=Response, responses=CSV_RESPONSE)
def admin_payout_batch_csv(batch_id: uuid.UUID) -> Response:
    raise not_implemented()
