"""Dispatch and courier status updates."""

import logging

from sqlalchemy import select

from kitaab.domain.context import Ctx
from kitaab.domain.enums import Actor, OrderStatus, PaymentMethod
from kitaab.domain.orders import service as orders
from kitaab.domain.payments import claim_event
from kitaab.models import Order
from kitaab.problems import ProblemError, invalid
from kitaab.providers.courier import CourierEvent, Shipment
from kitaab.providers.errors import ProviderError
from kitaab.schemas.admin import DispatchIn

log = logging.getLogger(__name__)


def dispatch(ctx: Ctx, order: Order, body: DispatchIn) -> Order:
    courier = ctx.services.couriers.get(body.courier_code)
    if courier is None:
        raise invalid("unknown-courier", "Choose a courier from the list")
    if not orders.can(order, Actor.ADMIN, OrderStatus.DISPATCHED):
        raise ProblemError(409, "invalid-transition", "The order is not ready for dispatch")
    if body.cn_number:
        cn, tracking_url = body.cn_number.strip(), body.tracking_url
    else:
        cod = (order.total_paisa or 0) if order.payment_method == PaymentMethod.COD else 0
        shipment = Shipment(
            order_code=order.code,
            recipient_name=order.ship_recipient_name or "",
            recipient_phone_e164=order.ship_recipient_phone_e164 or "",
            city_name=order.ship_city_name,
            address=f"{order.ship_street_address}, {order.ship_area}",
            landmark=order.ship_landmark or "",
            cod_amount_paisa=cod,
            pieces=1,
        )
        try:
            consignment = courier.create_consignment(shipment)
        except ProviderError as error:
            raise ProblemError(
                502,
                "courier-unavailable",
                "The courier could not book this parcel",
                f"{error.public_message}. Enter the CN number by hand to continue.",
            ) from error
        cn, tracking_url = consignment.cn_number, consignment.tracking_url
    order.courier_code = courier.code
    order.cn_number = cn
    order.tracking_url = tracking_url
    order.courier_status = "Booked"
    order.dispatched_at = ctx.now
    orders.transition(ctx, order, OrderStatus.DISPATCHED)
    return order


def apply_courier_events(ctx: Ctx, courier_code: str, events: list[CourierEvent]) -> int:
    """Webhook or poll results. Each event applies at most once."""
    applied = 0
    for event in events:
        if not claim_event(ctx, courier_code, f"courier:{event.event_id}"):
            continue
        order_id = ctx.session.scalar(
            select(Order.id).where(
                Order.courier_code == courier_code, Order.cn_number == event.cn_number
            )
        )
        if order_id is None:
            log.warning("courier event for unknown CN", extra={"courier": courier_code})
            continue
        order = orders.lock(ctx, order_id)
        order.courier_status = event.description[:120] or event.state
        if order.status == OrderStatus.DISPATCHED:
            if event.state == "DELIVERED":
                orders.transition(ctx, order, OrderStatus.DELIVERED, actor=Actor.SYSTEM)
            elif event.state in ("FAILED", "RETURNED"):
                orders.transition(
                    ctx,
                    order,
                    OrderStatus.DELIVERY_FAILED,
                    actor=Actor.SYSTEM,
                    reason=event.description or "Returned by courier",
                )
        applied += 1
    return applied


def poll_couriers(ctx: Ctx) -> int:
    """Scheduled job for couriers without webhooks."""
    total = 0
    for courier in ctx.services.couriers.all():
        if courier.supports_webhooks or not courier.has_api:
            continue
        cns = ctx.session.scalars(
            select(Order.cn_number).where(
                Order.courier_code == courier.code, Order.status == OrderStatus.DISPATCHED
            )
        ).all()
        for cn in cns:
            if not cn:
                continue
            try:
                events = courier.fetch_events(cn)
            except ProviderError:
                log.warning("courier poll failed", extra={"courier": courier.code})
                break
            total += apply_courier_events(ctx, courier.code, events)
    return total
