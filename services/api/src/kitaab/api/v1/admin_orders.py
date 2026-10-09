import uuid
from contextlib import suppress
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import Response
from sqlalchemy import ColumnElement, func, or_, select

from kitaab.api.v1.presenters import admin_order_detail, admin_order_summary, refund_out
from kitaab.domain import audit, payments, quotes, shipping
from kitaab.domain.context import Ctx
from kitaab.domain.enums import OrderStatus, OrderType, PaymentMethod, PaymentStatus, RefundStatus
from kitaab.domain.orders import service as orders
from kitaab.models import Order, Refund, User, Vendor
from kitaab.pdf.packing_slip import render_packing_slip
from kitaab.phone import InvalidPhoneError, normalize_pk_mobile
from kitaab.problems import PDF_RESPONSE, conflict, invalid, not_found
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
from kitaab.security.deps import admin_ctx

router = APIRouter(prefix="/admin", tags=["admin: orders"])


def _order(ctx: Ctx, order_id: uuid.UUID) -> Order:
    return orders.lock(ctx, order_id)


def _done(ctx: Ctx, order: Order, action: str, **details: object) -> AdminOrderDetail:
    audit.record(ctx, f"order.{action}", "order", order.id, status=order.status.value, **details)
    ctx.session.commit()
    ctx.session.refresh(order)
    return admin_order_detail(ctx, order)


def _vendor(ctx: Ctx, vendor_id: uuid.UUID) -> Vendor:
    vendor = ctx.session.get(Vendor, vendor_id)
    if vendor is None or not vendor.is_active:
        raise invalid("vendor-not-found", "Choose an active vendor")
    return vendor


@router.get("/orders")
def admin_list_orders(
    type: OrderType | None = None,
    status: list[OrderStatus] | None = Query(None),
    q: str | None = Query(None, max_length=100, description="Order code, phone or name"),
    created_from: datetime | None = None,
    created_to: datetime | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    ctx: Ctx = Depends(admin_ctx),
) -> AdminOrderPage:
    query = select(Order).join(User, User.id == Order.user_id)
    if type is not None:
        query = query.where(Order.type == type)
    if status:
        query = query.where(Order.status.in_(status))
    if created_from is not None:
        query = query.where(Order.created_at >= created_from)
    if created_to is not None:
        query = query.where(Order.created_at <= created_to)
    if q and q.strip():
        term = q.strip()
        conditions: list[ColumnElement[bool]] = [
            Order.code.ilike(f"%{term}%"),
            User.full_name.ilike(f"%{term}%"),
            Order.book_title.ilike(f"%{term}%"),
            Order.cn_number.ilike(f"%{term}%"),
        ]
        with suppress(InvalidPhoneError):
            conditions.append(User.phone_e164 == normalize_pk_mobile(term))
        query = query.where(or_(*conditions))
    total = ctx.session.scalar(select(func.count()).select_from(query.subquery())) or 0
    rows = ctx.session.scalars(
        query.order_by(Order.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    )
    return AdminOrderPage(
        items=[admin_order_summary(o) for o in rows], total=total, page=page, page_size=page_size
    )


@router.get("/orders/{order_id}")
def admin_get_order(order_id: uuid.UUID, ctx: Ctx = Depends(admin_ctx)) -> AdminOrderDetail:
    order = ctx.session.get(Order, order_id)
    if order is None:
        raise not_found("Order")
    return admin_order_detail(ctx, order)


@router.get("/orders/{order_id}/file-url")
def admin_file_url(order_id: uuid.UUID, ctx: Ctx = Depends(admin_ctx)) -> FileUrl:
    """Short-lived (5 minute) link to the customer's PDF. Logged in the audit log."""
    order = ctx.session.get(Order, order_id)
    if order is None or order.upload is None or order.upload.object_key is None:
        raise not_found("File")
    ttl = ctx.services.settings.download_url_ttl_seconds
    url = ctx.services.store.presign_get(order.upload.object_key, ttl, f"{order.code}.pdf")
    audit.record(ctx, "file.download", "order", order.id, upload_id=str(order.upload.id))
    ctx.session.commit()
    return FileUrl(url=url, expires_at=ctx.now + timedelta(seconds=ttl))


@router.get("/orders/{order_id}/packing-slip", response_class=Response, responses=PDF_RESPONSE)
def admin_packing_slip(order_id: uuid.UUID, ctx: Ctx = Depends(admin_ctx)) -> Response:
    order = ctx.session.get(Order, order_id)
    if order is None:
        raise not_found("Order")
    pdf = render_packing_slip(order, ctx.services.couriers.name_of(order.courier_code))
    return Response(
        pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="packing-slip-{order.code}.pdf"'},
    )


@router.post("/orders/{order_id}/start-verification")
def admin_start_verification(
    order_id: uuid.UUID, ctx: Ctx = Depends(admin_ctx)
) -> AdminOrderDetail:
    """PRINT: PLACED to VERIFYING."""
    order = _order(ctx, order_id)
    orders.transition(ctx, order, OrderStatus.VERIFYING)
    return _done(ctx, order, "start-verification")


@router.post("/orders/{order_id}/approve")
def admin_approve(
    order_id: uuid.UUID, body: ApproveAndAssign, ctx: Ctx = Depends(admin_ctx)
) -> AdminOrderDetail:
    """PRINT: approve the file and assign a vendor (VERIFYING to ASSIGNED)."""
    order = _order(ctx, order_id)
    vendor = _vendor(ctx, body.vendor_id)
    if order.upload is None or order.upload.object_key is None:
        raise conflict("file-missing", "The file is no longer available")
    order.vendor_id = vendor.id
    order.vendor_cost_paisa = body.vendor_cost_paisa
    order.assigned_at = ctx.now
    orders.transition(ctx, order, OrderStatus.ASSIGNED)
    return _done(
        ctx, order, "approve", vendor_id=str(vendor.id), vendor_cost_paisa=body.vendor_cost_paisa
    )


@router.post("/orders/{order_id}/reject")
def admin_reject(
    order_id: uuid.UUID, body: ReasonIn, ctx: Ctx = Depends(admin_ctx)
) -> AdminOrderDetail:
    """PRINT: reject with a reason shown to the customer."""
    order = _order(ctx, order_id)
    orders.transition(ctx, order, OrderStatus.REJECTED, reason=body.reason)
    return _done(ctx, order, "reject")


@router.post("/orders/{order_id}/quote/preview")
def admin_preview_quote(
    order_id: uuid.UUID, body: QuoteIn, ctx: Ctx = Depends(admin_ctx)
) -> QuotePreview:
    """SOURCE: what the calculator proposes for these options."""
    order = ctx.session.get(Order, order_id)
    if order is None:
        raise not_found("Order")
    breakdown, digital, cod = quotes.calculate_quote(ctx, order, body)
    return QuotePreview(breakdown=breakdown, total_if_digital_paisa=digital, total_if_cod_paisa=cod)


@router.post("/orders/{order_id}/quote")
def admin_send_quote(
    order_id: uuid.UUID, body: QuoteIn, ctx: Ctx = Depends(admin_ctx)
) -> AdminOrderDetail:
    """SOURCE: send a quote to the customer (REQUESTED to QUOTED)."""
    order = _order(ctx, order_id)
    quote = quotes.send_quote(ctx, order, body)
    return _done(
        ctx,
        order,
        "quote",
        goods_paisa=quote.goods_paisa,
        overridden=quote.override_reason is not None,
    )


@router.post("/orders/{order_id}/start-sourcing")
def admin_start_sourcing(
    order_id: uuid.UUID, body: StartSourcing, ctx: Ctx = Depends(admin_ctx)
) -> AdminOrderDetail:
    """SOURCE: ACCEPTED to SOURCING, optionally with a vendor."""
    order = _order(ctx, order_id)
    if order.payment_status != PaymentStatus.PAID and order.payment_method != PaymentMethod.COD:
        raise conflict("payment-pending", "Wait for the customer's online payment before sourcing")
    if body.vendor_id is not None:
        vendor = _vendor(ctx, body.vendor_id)
        order.vendor_id = vendor.id
        order.vendor_cost_paisa = body.vendor_cost_paisa or 0
        order.assigned_at = ctx.now
    orders.transition(ctx, order, OrderStatus.SOURCING)
    return _done(
        ctx, order, "start-sourcing", vendor_id=str(body.vendor_id) if body.vendor_id else None
    )


@router.post("/orders/{order_id}/mark-unavailable")
def admin_mark_unavailable(
    order_id: uuid.UUID, body: ReasonIn, ctx: Ctx = Depends(admin_ctx)
) -> AdminOrderDetail:
    order = _order(ctx, order_id)
    orders.transition(ctx, order, OrderStatus.UNAVAILABLE, reason=body.reason)
    return _done(ctx, order, "mark-unavailable")


@router.post("/orders/{order_id}/start-printing")
def admin_start_printing(order_id: uuid.UUID, ctx: Ctx = Depends(admin_ctx)) -> AdminOrderDetail:
    """PRINT: ASSIGNED to IN_PRINT on the vendor's behalf."""
    order = _order(ctx, order_id)
    orders.transition(ctx, order, OrderStatus.IN_PRINT)
    return _done(ctx, order, "start-printing")


@router.post("/orders/{order_id}/ready-for-dispatch")
def admin_ready_for_dispatch(
    order_id: uuid.UUID, ctx: Ctx = Depends(admin_ctx)
) -> AdminOrderDetail:
    order = _order(ctx, order_id)
    orders.transition(ctx, order, OrderStatus.READY_FOR_DISPATCH)
    return _done(ctx, order, "ready-for-dispatch")


@router.post("/orders/{order_id}/dispatch")
def admin_dispatch(
    order_id: uuid.UUID, body: DispatchIn, ctx: Ctx = Depends(admin_ctx)
) -> AdminOrderDetail:
    """Book the courier (or record a manual CN) and mark the order dispatched."""
    order = _order(ctx, order_id)
    shipping.dispatch(ctx, order, body)
    return _done(
        ctx, order, "dispatch", courier=order.courier_code, manual_cn=body.cn_number is not None
    )


@router.post("/orders/{order_id}/mark-delivered")
def admin_mark_delivered(order_id: uuid.UUID, ctx: Ctx = Depends(admin_ctx)) -> AdminOrderDetail:
    order = _order(ctx, order_id)
    orders.transition(ctx, order, OrderStatus.DELIVERED)
    return _done(ctx, order, "mark-delivered")


@router.post("/orders/{order_id}/mark-delivery-failed")
def admin_mark_delivery_failed(
    order_id: uuid.UUID, body: ReasonIn, ctx: Ctx = Depends(admin_ctx)
) -> AdminOrderDetail:
    order = _order(ctx, order_id)
    orders.transition(ctx, order, OrderStatus.DELIVERY_FAILED, reason=body.reason)
    return _done(ctx, order, "mark-delivery-failed")


@router.post("/orders/{order_id}/cancel")
def admin_cancel(
    order_id: uuid.UUID, body: ReasonIn, ctx: Ctx = Depends(admin_ctx)
) -> AdminOrderDetail:
    order = _order(ctx, order_id)
    orders.transition(ctx, order, OrderStatus.CANCELLED, reason=body.reason)
    return _done(ctx, order, "cancel")


@router.post("/orders/{order_id}/refunds", status_code=status.HTTP_201_CREATED)
def admin_create_refund(
    order_id: uuid.UUID, body: RefundCreate, ctx: Ctx = Depends(admin_ctx)
) -> RefundOut:
    """Manual refund, for example after a failed delivery."""
    order = _order(ctx, order_id)
    refund = payments.create_manual_refund(ctx, order, body.amount_paisa, body.reason)
    audit.record(ctx, "refund.create", "order", order.id, amount_paisa=body.amount_paisa)
    ctx.session.commit()
    return refund_out(refund, order.code)


@router.get("/refunds")
def admin_list_refunds(
    status: RefundStatus | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    ctx: Ctx = Depends(admin_ctx),
) -> RefundPage:
    query = select(Refund, Order.code).join(Order, Order.id == Refund.order_id)
    if status is not None:
        query = query.where(Refund.status == status)
    total = ctx.session.scalar(select(func.count()).select_from(query.subquery())) or 0
    rows = ctx.session.execute(
        query.order_by(Refund.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    )
    return RefundPage(
        items=[refund_out(r, code) for r, code in rows], total=total, page=page, page_size=page_size
    )


@router.post("/refunds/{refund_id}/mark-processed")
def admin_mark_refund_processed(
    refund_id: uuid.UUID, body: RefundProcess, ctx: Ctx = Depends(admin_ctx)
) -> RefundOut:
    refund = ctx.session.get(Refund, refund_id, with_for_update=True)
    if refund is None:
        raise not_found("Refund")
    payments.mark_refund_processed(ctx, refund, body.reference)
    audit.record(ctx, "refund.processed", "refund", refund.id)
    ctx.session.commit()
    order = ctx.session.get(Order, refund.order_id)
    return refund_out(refund, order.code if order else "")


@router.get("/couriers")
def admin_list_couriers(ctx: Ctx = Depends(admin_ctx)) -> list[CourierOption]:
    return [
        CourierOption(code=c.code, name=c.name, has_api=c.has_api)
        for c in ctx.services.couriers.all()
    ]
