import uuid
from datetime import datetime

from fastapi import APIRouter, Query, status
from fastapi.responses import Response

from kitaab.domain.enums import OrderStatus, OrderType, RefundStatus
from kitaab.problems import PDF_RESPONSE, not_implemented
from kitaab.schemas.admin import (
    AdminOrderDetail,
    AdminOrderPage,
    ApproveAndAssign,
    CourierOption,
    DispatchIn,
    QuoteIn,
    QuotePreview,
    ReasonIn,
    RefundCreate,
    RefundOut,
    RefundPage,
    RefundProcess,
    StartSourcing,
)
from kitaab.schemas.common import FileUrl

router = APIRouter(prefix="/admin", tags=["admin: orders"])


@router.get("/orders")
def admin_list_orders(
    type: OrderType | None = None,
    status: list[OrderStatus] | None = Query(None),
    q: str | None = Query(None, max_length=100, description="Order code, phone or name"),
    created_from: datetime | None = None,
    created_to: datetime | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
) -> AdminOrderPage:
    raise not_implemented()


@router.get("/orders/{order_id}")
def admin_get_order(order_id: uuid.UUID) -> AdminOrderDetail:
    raise not_implemented()


@router.get("/orders/{order_id}/file-url")
def admin_file_url(order_id: uuid.UUID) -> FileUrl:
    """Short-lived (5 minute) link to the customer's PDF. Logged in the audit log."""
    raise not_implemented()


@router.get("/orders/{order_id}/packing-slip", response_class=Response, responses=PDF_RESPONSE)
def admin_packing_slip(order_id: uuid.UUID) -> Response:
    raise not_implemented()


@router.post("/orders/{order_id}/start-verification")
def admin_start_verification(order_id: uuid.UUID) -> AdminOrderDetail:
    """PRINT: PLACED to VERIFYING."""
    raise not_implemented()


@router.post("/orders/{order_id}/approve")
def admin_approve(order_id: uuid.UUID, body: ApproveAndAssign) -> AdminOrderDetail:
    """PRINT: approve the file and assign a vendor (VERIFYING to ASSIGNED)."""
    raise not_implemented()


@router.post("/orders/{order_id}/reject")
def admin_reject(order_id: uuid.UUID, body: ReasonIn) -> AdminOrderDetail:
    """PRINT: reject with a reason shown to the customer."""
    raise not_implemented()


@router.post("/orders/{order_id}/quote/preview")
def admin_preview_quote(order_id: uuid.UUID, body: QuoteIn) -> QuotePreview:
    """SOURCE: what the calculator proposes for these options."""
    raise not_implemented()


@router.post("/orders/{order_id}/quote")
def admin_send_quote(order_id: uuid.UUID, body: QuoteIn) -> AdminOrderDetail:
    """SOURCE: send a quote to the customer (REQUESTED to QUOTED)."""
    raise not_implemented()


@router.post("/orders/{order_id}/start-sourcing")
def admin_start_sourcing(order_id: uuid.UUID, body: StartSourcing) -> AdminOrderDetail:
    """SOURCE: ACCEPTED to SOURCING, optionally with a vendor."""
    raise not_implemented()


@router.post("/orders/{order_id}/mark-unavailable")
def admin_mark_unavailable(order_id: uuid.UUID, body: ReasonIn) -> AdminOrderDetail:
    raise not_implemented()


@router.post("/orders/{order_id}/start-printing")
def admin_start_printing(order_id: uuid.UUID) -> AdminOrderDetail:
    """PRINT: ASSIGNED to IN_PRINT on the vendor's behalf."""
    raise not_implemented()


@router.post("/orders/{order_id}/ready-for-dispatch")
def admin_ready_for_dispatch(order_id: uuid.UUID) -> AdminOrderDetail:
    raise not_implemented()


@router.post("/orders/{order_id}/dispatch")
def admin_dispatch(order_id: uuid.UUID, body: DispatchIn) -> AdminOrderDetail:
    """Book the courier (or record a manual CN) and mark the order dispatched."""
    raise not_implemented()


@router.post("/orders/{order_id}/mark-delivered")
def admin_mark_delivered(order_id: uuid.UUID) -> AdminOrderDetail:
    raise not_implemented()


@router.post("/orders/{order_id}/mark-delivery-failed")
def admin_mark_delivery_failed(order_id: uuid.UUID, body: ReasonIn) -> AdminOrderDetail:
    raise not_implemented()


@router.post("/orders/{order_id}/cancel")
def admin_cancel(order_id: uuid.UUID, body: ReasonIn) -> AdminOrderDetail:
    raise not_implemented()


@router.post("/orders/{order_id}/refunds", status_code=status.HTTP_201_CREATED)
def admin_create_refund(order_id: uuid.UUID, body: RefundCreate) -> RefundOut:
    """Manual refund, for example after a failed delivery."""
    raise not_implemented()


@router.get("/refunds")
def admin_list_refunds(
    status: RefundStatus | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
) -> RefundPage:
    raise not_implemented()


@router.post("/refunds/{refund_id}/mark-processed")
def admin_mark_refund_processed(refund_id: uuid.UUID, body: RefundProcess) -> RefundOut:
    raise not_implemented()


@router.get("/couriers")
def admin_list_couriers() -> list[CourierOption]:
    raise not_implemented()
