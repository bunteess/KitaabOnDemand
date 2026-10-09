import uuid
from typing import Literal

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import func, select

from kitaab.api.v1.presenters import order_detail, order_summary
from kitaab.domain import quotes
from kitaab.domain.context import Ctx
from kitaab.domain.enums import TERMINAL_STATUSES, Actor, OrderStatus
from kitaab.domain.orders import service as orders
from kitaab.models import Order
from kitaab.problems import conflict, not_found
from kitaab.schemas.orders import (
    CancelRequest,
    CheckoutSession,
    OrderDetail,
    OrderPage,
    PrintOrderCreate,
    QuoteAccept,
    SourceOrderCreate,
)
from kitaab.security.deps import customer_ctx, me

router = APIRouter(prefix="/orders", tags=["orders"])

PAST = TERMINAL_STATUSES | {OrderStatus.DELIVERED}


def _owned(ctx: Ctx, order_id: uuid.UUID, *, lock: bool = False) -> Order:
    order = orders.lock(ctx, order_id) if lock else ctx.session.get(Order, order_id)
    if order is None:
        raise not_found("Order")
    orders.ensure_owner(order, me(ctx))
    return order


def _detail(ctx: Ctx, order: Order) -> OrderDetail:
    ctx.session.commit()
    ctx.session.refresh(order)
    return order_detail(ctx, order)


@router.post("/print", status_code=status.HTTP_201_CREATED)
def create_print_order(body: PrintOrderCreate, ctx: Ctx = Depends(customer_ctx)) -> OrderDetail:
    """Order prints of a validated upload. Digital payments return a checkout URL."""
    return _detail(ctx, orders.create_print_order(ctx, me(ctx), body))


@router.post("/source", status_code=status.HTTP_201_CREATED)
def create_source_order(body: SourceOrderCreate, ctx: Ctx = Depends(customer_ctx)) -> OrderDetail:
    """Ask us to find a book. An admin sends a quote."""
    return _detail(ctx, orders.create_source_order(ctx, me(ctx), body))


@router.get("")
def list_orders(
    group: Literal["active", "past", "all"] = "all",
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=50),
    ctx: Ctx = Depends(customer_ctx),
) -> OrderPage:
    query = select(Order).where(Order.user_id == me(ctx).id)
    if group == "active":
        query = query.where(Order.status.not_in(PAST))
    elif group == "past":
        query = query.where(Order.status.in_(PAST))
    total = ctx.session.scalar(select(func.count()).select_from(query.subquery())) or 0
    rows = ctx.session.scalars(
        query.order_by(Order.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    )
    return OrderPage(
        items=[order_summary(o) for o in rows], total=total, page=page, page_size=page_size
    )


@router.get("/{order_id}")
def get_order(order_id: uuid.UUID, ctx: Ctx = Depends(customer_ctx)) -> OrderDetail:
    return order_detail(ctx, _owned(ctx, order_id))


@router.post("/{order_id}/cancel")
def cancel_order(
    order_id: uuid.UUID, body: CancelRequest, ctx: Ctx = Depends(customer_ctx)
) -> OrderDetail:
    order = _owned(ctx, order_id, lock=True)
    if not orders.can(order, Actor.USER, OrderStatus.CANCELLED):
        raise conflict(
            "cannot-cancel", "This order can no longer be cancelled. Contact support for help."
        )
    orders.transition(
        ctx,
        order,
        OrderStatus.CANCELLED,
        actor=Actor.USER,
        reason=body.reason or "Cancelled by customer",
    )
    return _detail(ctx, order)


@router.post("/{order_id}/quote/accept")
def accept_quote(
    order_id: uuid.UUID, body: QuoteAccept, ctx: Ctx = Depends(customer_ctx)
) -> OrderDetail:
    order = _owned(ctx, order_id, lock=True)
    quotes.accept(ctx, order, body.payment_method, body.expected_total_paisa)
    return _detail(ctx, order)


@router.post("/{order_id}/quote/decline")
def decline_quote(order_id: uuid.UUID, ctx: Ctx = Depends(customer_ctx)) -> OrderDetail:
    order = _owned(ctx, order_id, lock=True)
    quotes.decline(ctx, order)
    return _detail(ctx, order)


@router.post("/{order_id}/payments", status_code=status.HTTP_201_CREATED)
def retry_payment(order_id: uuid.UUID, ctx: Ctx = Depends(customer_ctx)) -> CheckoutSession:
    """Start a new checkout for an order whose digital payment is still pending."""
    order = _owned(ctx, order_id, lock=True)
    payment = orders.retry_payment(ctx, order)
    ctx.session.commit()
    return CheckoutSession(payment_id=payment.id, checkout_url=payment.checkout_url or "")
