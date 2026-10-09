"""Applying payment gateway events (webhooks) and processing refunds."""

import logging
import uuid
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from kitaab.domain import ledger, notifications
from kitaab.domain import notification_texts as texts
from kitaab.domain.context import Ctx
from kitaab.domain.enums import (
    TERMINAL_STATUSES,
    Actor,
    NotificationKind,
    OrderStatus,
    PaymentStatus,
    RefundStatus,
)
from kitaab.domain.orders import service as orders
from kitaab.models import Order, Payment, Refund, WebhookEvent
from kitaab.problems import conflict, not_found
from kitaab.providers.errors import ProviderError, RefundNotSupported
from kitaab.providers.payment import PaymentEvent

log = logging.getLogger(__name__)


def claim_event(ctx: Ctx, provider: str, event_key: str) -> bool:
    """Record a webhook event; False if it was already processed (idempotency)."""
    try:
        with ctx.session.begin_nested():
            ctx.session.add(
                WebhookEvent(provider=provider, event_key=event_key[:200], received_at=ctx.now)
            )
    except IntegrityError:
        return False
    return True


def apply_payment_event(ctx: Ctx, provider: str, event: PaymentEvent) -> str:
    """Returns "processed", "duplicate" or "ignored"."""
    if not claim_event(ctx, provider, f"payment:{event.event_id}"):
        return "duplicate"
    payment = ctx.session.scalar(
        select(Payment)
        .where(Payment.provider == provider, Payment.provider_ref == event.provider_ref)
        .with_for_update()
    )
    if payment is None:
        log.warning("payment event for unknown reference", extra={"provider": provider})
        return "ignored"
    if payment.status in (PaymentStatus.PAID, PaymentStatus.REFUNDED):
        return "ignored"
    order = orders.lock(ctx, payment.order_id)
    if event.status == "FAILED" or event.amount_paisa not in (None, payment.amount_paisa):
        if payment.status != PaymentStatus.PENDING:
            return "ignored"
        if event.status == "PAID":
            log.error("payment amount mismatch", extra={"payment_id": str(payment.id)})
        _fail(ctx, order, payment, event.failure_reason or "Declined")
        return "processed"

    # A FAILED payment here is an attempt we closed ourselves (order cancelled,
    # checkout replaced, payment window over) that the customer paid anyway.
    late = payment.status == PaymentStatus.FAILED
    payment.status = PaymentStatus.PAID
    payment.paid_at = ctx.now
    payment.checkout_url = None
    payment.failed_at = None
    payment.failure_reason = None
    ledger.record_revenue(ctx, order, payment)
    if order.status in TERMINAL_STATUSES or order.payment_status == PaymentStatus.PAID:
        # Paid for a closed order, or paid twice: give this payment back.
        orders.refund_payment(ctx, order, payment, reason="Payment received after the order closed")
        return "processed"
    if late:
        for other in ctx.session.scalars(
            select(Payment).where(
                Payment.order_id == order.id,
                Payment.status == PaymentStatus.PENDING,
                Payment.id != payment.id,
            )
        ):
            other.status = PaymentStatus.FAILED
            other.failed_at = ctx.now
            other.failure_reason = "Paid with an earlier attempt"
    order.payment_status = PaymentStatus.PAID
    notifications.notify(
        ctx,
        order.user_id,
        NotificationKind.PAYMENT,
        *texts.payment_received(order, payment.amount_paisa),
        order=order,
    )
    if order.status == OrderStatus.PENDING_PAYMENT:
        orders.transition(ctx, order, OrderStatus.PLACED, actor=Actor.SYSTEM)
    else:
        orders.try_complete(ctx, order)
    return "processed"


def _fail(ctx: Ctx, order: Order, payment: Payment, reason: str) -> None:
    payment.status = PaymentStatus.FAILED
    payment.failed_at = ctx.now
    payment.failure_reason = reason[:300]
    order.payment_status = PaymentStatus.FAILED
    notifications.notify(
        ctx, order.user_id, NotificationKind.PAYMENT, *texts.payment_failed(order), order=order
    )


def expire_pending_payments(ctx: Ctx) -> int:
    """Scheduled job: cancel PRINT orders still unpaid after PENDING_PAYMENT_TTL_HOURS."""
    cutoff = ctx.now - timedelta(hours=ctx.services.settings.pending_payment_ttl_hours)
    ids = ctx.session.scalars(
        select(Order.id).where(
            Order.status == OrderStatus.PENDING_PAYMENT, Order.created_at <= cutoff
        )
    ).all()
    for order_id in ids:
        order = orders.lock(ctx, order_id)
        if order.status == OrderStatus.PENDING_PAYMENT:
            orders.transition(
                ctx,
                order,
                OrderStatus.CANCELLED,
                actor=Actor.SYSTEM,
                reason="Payment was not completed in time",
            )
    return len(ids)


def process_refund(ctx: Ctx, refund_id: uuid.UUID) -> bool:
    """Try the gateway. If it cannot refund by API, the refund stays PENDING for an admin."""
    refund = ctx.session.get(Refund, refund_id, with_for_update=True)
    if refund is None or refund.status != RefundStatus.PENDING or refund.payment_id is None:
        return False
    payment = ctx.session.get(Payment, refund.payment_id)
    provider = ctx.services.payments.get(payment.provider) if payment else None
    if payment is None or provider is None or payment.provider_ref is None:
        return False
    try:
        reference = provider.refund(payment.provider_ref, refund.amount_paisa)
    except RefundNotSupported:
        return False
    except ProviderError:
        log.warning(
            "gateway refund failed; left for manual processing", extra={"refund_id": str(refund_id)}
        )
        return False
    mark_refund_processed(ctx, refund, reference)
    return True


def mark_refund_processed(ctx: Ctx, refund: Refund, reference: str) -> Refund:
    if refund.status == RefundStatus.PROCESSED:
        raise conflict("already-processed", "This refund is already processed")
    order = ctx.session.get(Order, refund.order_id)
    if order is None:
        raise not_found("Order")
    refund.status = RefundStatus.PROCESSED
    refund.reference = reference
    refund.processed_at = ctx.now
    refund.processed_by_id = ctx.user.id if ctx.user else None
    payment = ctx.session.get(Payment, refund.payment_id) if refund.payment_id else None
    if payment is not None and refund.amount_paisa >= payment.amount_paisa:
        payment.status = PaymentStatus.REFUNDED
        still_paid = ctx.session.scalar(
            select(Payment.id).where(
                Payment.order_id == order.id, Payment.status == PaymentStatus.PAID
            )
        )
        if still_paid is None:
            order.payment_status = PaymentStatus.REFUNDED
    ledger.record_refund(ctx, refund, order)
    return refund


def create_manual_refund(ctx: Ctx, order: Order, amount_paisa: int, reason: str) -> Refund:
    paid = ctx.session.scalars(
        select(Payment).where(Payment.order_id == order.id, Payment.status == PaymentStatus.PAID)
    ).all()
    refunded = sum(
        r.amount_paisa
        for r in ctx.session.scalars(select(Refund).where(Refund.order_id == order.id))
    )
    available = sum(p.amount_paisa for p in paid) - refunded
    if amount_paisa > available:
        raise conflict(
            "refund-too-large", "The refund is more than what was paid", available_paisa=available
        )
    refund = Refund(
        order_id=order.id,
        payment_id=paid[0].id if paid else None,
        amount_paisa=amount_paisa,
        status=RefundStatus.PENDING,
        reason=reason,
        created_by_id=ctx.user.id if ctx.user else None,
        created_at=ctx.now,
    )
    ctx.session.add(refund)
    ctx.session.flush()
    return refund
