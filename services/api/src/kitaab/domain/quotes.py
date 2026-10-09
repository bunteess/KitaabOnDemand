"""SOURCE quotes: the admin proposes a price, the customer accepts or declines."""

from datetime import timedelta

from sqlalchemy import select

from kitaab.domain import pricing_store
from kitaab.domain.app_settings import load as load_settings
from kitaab.domain.context import Ctx
from kitaab.domain.enums import (
    Actor,
    OrderStatus,
    OrderType,
    PaymentMethod,
    PaymentStatus,
    QuoteStatus,
)
from kitaab.domain.orders import service as orders
from kitaab.domain.pricing import PriceBreakdown, PriceInput, PricingError, calculate
from kitaab.models import Order, Quote
from kitaab.problems import conflict, invalid
from kitaab.schemas.admin import QuoteIn


def _require_source(order: Order) -> None:
    if order.type != OrderType.SOURCE:
        raise conflict("wrong-order-type", "Only book requests get quotes")


def calculate_quote(ctx: Ctx, order: Order, body: QuoteIn) -> tuple[PriceBreakdown, int, int]:
    """Breakdown without a payment method, and the totals for online and COD payment."""
    _require_source(order)
    if body.goods_override_paisa is not None and not (
        body.override_reason and body.override_reason.strip()
    ):
        raise invalid("override-reason-required", "Give a reason for overriding the price")
    rules, version = pricing_store.active(ctx)
    try:
        breakdown = calculate(
            rules,
            version,
            PriceInput(
                pages=body.pages,
                paper=body.paper,
                binding=body.binding,
                copies=body.copies,
                zone=order.ship_zone_code,
                sourcing_cost_paisa=body.sourcing_cost_paisa,
                goods_override_paisa=body.goods_override_paisa,
            ),
        )
    except PricingError as error:
        raise orders.pricing_problem(error) from error
    return breakdown, breakdown.total_paisa, breakdown.total_paisa + rules.cod_fee_paisa


def open_quote(ctx: Ctx, order: Order) -> Quote | None:
    return ctx.session.scalar(
        select(Quote)
        .where(Quote.order_id == order.id, Quote.status == QuoteStatus.OPEN)
        .order_by(Quote.created_at.desc())
        .limit(1)
    )


def send_quote(ctx: Ctx, order: Order, body: QuoteIn) -> Quote:
    breakdown, _, _ = calculate_quote(ctx, order, body)
    hours = body.valid_hours or load_settings(ctx).quote_validity_hours
    quote = Quote(
        order_id=order.id,
        status=QuoteStatus.OPEN,
        pages=body.pages,
        paper=body.paper,
        binding=body.binding,
        copies=body.copies,
        sourcing_cost_paisa=body.sourcing_cost_paisa,
        calculated_goods_paisa=breakdown.calculated_goods_paisa,
        goods_paisa=breakdown.goods_paisa,
        override_reason=body.override_reason if body.goods_override_paisa is not None else None,
        pricing_config_version=breakdown.config_version,
        breakdown=breakdown.model_dump(mode="json"),
        valid_until=ctx.now + timedelta(hours=hours),
        created_by_id=ctx.user.id if ctx.user else None,
        created_at=ctx.now,
    )
    ctx.session.add(quote)
    ctx.session.flush()
    orders.transition(ctx, order, OrderStatus.QUOTED)
    return quote


def totals(ctx: Ctx, quote: Quote) -> tuple[int, int, int]:
    """(digital total, COD total, COD fee) from the quote's own pricing version."""
    breakdown = PriceBreakdown.model_validate(quote.breakdown)
    cod_fee = pricing_store.by_version(ctx, quote.pricing_config_version).cod_fee_paisa
    return breakdown.total_paisa, breakdown.total_paisa + cod_fee, cod_fee


def accept(ctx: Ctx, order: Order, method: PaymentMethod, expected_total_paisa: int) -> Order:
    quote = open_quote(ctx, order)
    if order.status != OrderStatus.QUOTED or quote is None:
        raise conflict("no-open-quote", "There is no price waiting for you on this order")
    if quote.valid_until <= ctx.now:
        expire(ctx, order)
        # Keep the expiry even though this request fails.
        ctx.session.commit()
        raise conflict("quote-expired", "This price has expired")
    orders.check_method_enabled(ctx, method)
    digital_total, cod_total, cod_fee = totals(ctx, quote)
    total = cod_total if method == PaymentMethod.COD else digital_total
    orders.check_cod_allowed(ctx, method, total)
    if expected_total_paisa != total:
        raise conflict("price-mismatch", "The price has changed", total_paisa=total)

    breakdown = PriceBreakdown.model_validate(quote.breakdown).model_copy(
        update={
            "payment_method": method,
            "cod_fee_paisa": cod_fee if method == PaymentMethod.COD else 0,
            "total_paisa": total,
        }
    )
    order.pages, order.paper, order.binding, order.copies = (
        quote.pages,
        quote.paper,
        quote.binding,
        quote.copies,
    )
    order.payment_method = method
    order.payment_status = PaymentStatus.PENDING
    order.pricing_config_version = quote.pricing_config_version
    order.price_breakdown = breakdown.model_dump(mode="json")
    order.total_paisa = total
    quote.status = QuoteStatus.ACCEPTED
    quote.responded_at = ctx.now
    orders.transition(ctx, order, OrderStatus.ACCEPTED, actor=Actor.USER)
    orders.start_payment(ctx, order)
    return order


def decline(ctx: Ctx, order: Order) -> Order:
    if order.status != OrderStatus.QUOTED:
        raise conflict("no-open-quote", "There is no price waiting for you on this order")
    orders.transition(ctx, order, OrderStatus.DECLINED, actor=Actor.USER)
    return order


def expire(ctx: Ctx, order: Order) -> None:
    orders.transition(ctx, order, OrderStatus.QUOTE_EXPIRED, actor=Actor.SYSTEM)


def expire_due(ctx: Ctx) -> int:
    """Scheduled job: move quotes past their validity to QUOTE_EXPIRED."""
    due = ctx.session.scalars(
        select(Order.id)
        .join(Quote, Quote.order_id == Order.id)
        .where(
            Order.status == OrderStatus.QUOTED,
            Quote.status == QuoteStatus.OPEN,
            Quote.valid_until <= ctx.now,
        )
    ).all()
    count = 0
    for order_id in set(due):
        order = orders.lock(ctx, order_id)
        if order.status == OrderStatus.QUOTED:
            expire(ctx, order)
            count += 1
    return count
