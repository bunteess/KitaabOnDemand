"""Creating orders and moving them through the state machine."""

import secrets
import uuid
from functools import partial

from sqlalchemy import select
from sqlalchemy.orm import Session

from kitaab.domain import ledger, notifications, pricing_store
from kitaab.domain import notification_texts as texts
from kitaab.domain.app_settings import load as load_settings
from kitaab.domain.context import Ctx
from kitaab.domain.enums import (
    DIGITAL_METHODS,
    Actor,
    NotificationKind,
    OrderStatus,
    OrderType,
    PaymentMethod,
    PaymentStatus,
    QuoteStatus,
    RefundStatus,
    Role,
    UploadStatus,
)
from kitaab.domain.orders import state_machine as sm
from kitaab.domain.orders.state_machine import Effect, Transition
from kitaab.domain.orders.timeline import EXIT_STATUSES
from kitaab.domain.pricing import PriceBreakdown, PriceInput, PricingError, calculate
from kitaab.models import (
    Address,
    City,
    Order,
    OrderStatusHistory,
    Payment,
    Quote,
    Refund,
    Upload,
    User,
)
from kitaab.problems import ProblemError, conflict, forbidden, invalid, not_found
from kitaab.providers.errors import ProviderError
from kitaab.schemas.orders import PrintOrderCreate, SourceOrderCreate
from kitaab.tx import after_commit

_CODE_ALPHABET = "23456789ABCDEFGHJKMNPQRSTVWXYZ"  # no 0/O, 1/I/L, U


def new_order_code(session: Session) -> str:
    for _ in range(10):
        code = "KD" + "".join(secrets.choice(_CODE_ALPHABET) for _ in range(7))
        if session.scalar(select(Order.id).where(Order.code == code)) is None:
            return code
    raise RuntimeError("could not generate a unique order code")


def lock(ctx: Ctx, order_id: uuid.UUID) -> Order:
    """Load an order for update, so concurrent webhooks and admins cannot race."""
    order = ctx.session.scalar(select(Order).where(Order.id == order_id).with_for_update(of=Order))
    if order is None:
        raise not_found("Order")
    return order


def actor_for(user: User | None) -> Actor:
    if user is None:
        return Actor.SYSTEM
    return {Role.ADMIN: Actor.ADMIN, Role.VENDOR: Actor.VENDOR, Role.CUSTOMER: Actor.USER}[
        user.role
    ]


# -- transitions ------------------------------------------------------------------


def transition(
    ctx: Ctx,
    order: Order,
    target: OrderStatus,
    *,
    actor: Actor | None = None,
    reason: str | None = None,
) -> Transition:
    actor = actor or actor_for(ctx.user)
    rule = sm.find(order.type, order.status, target)
    if rule is None or actor not in rule.actors:
        raise conflict(
            "invalid-transition",
            "This change is not allowed in the order's current state",
            f"{order.status.value} to {target.value} is not allowed for {actor.value}",
            from_status=order.status.value,
            to_status=target.value,
        )
    if rule.needs_reason and not (reason and reason.strip()):
        raise invalid("reason-required", "Please give a reason")
    previous = order.status
    order.status = target
    order.updated_at = ctx.now
    if target in EXIT_STATUSES and reason:
        order.exit_reason = reason.strip()[:500]
    ctx.session.add(
        OrderStatusHistory(
            order_id=order.id,
            from_status=previous,
            to_status=target,
            actor=actor,
            actor_user_id=ctx.user.id if ctx.user and actor != Actor.SYSTEM else None,
            reason=reason,
            created_at=ctx.now,
        )
    )
    for effect in rule.effects:
        _apply(ctx, order, effect)
    ctx.session.flush()
    return rule


def _apply(ctx: Ctx, order: Order, effect: Effect) -> None:
    if effect == Effect.NOTIFY:
        notifications.notify_order_status(ctx, order)
    elif effect == Effect.MARK_TERMINAL:
        order.terminal_at = ctx.now
    elif effect == Effect.CLOSE_PENDING_PAYMENT:
        for payment in _payments(ctx, order, PaymentStatus.PENDING):
            payment.status = PaymentStatus.FAILED
            payment.failed_at = ctx.now
            payment.failure_reason = f"Order {order.status.value.lower()}"
        if order.payment_status == PaymentStatus.PENDING:
            order.payment_status = PaymentStatus.FAILED
    elif effect == Effect.REFUND_IF_PAID:
        create_refunds_for_paid(ctx, order, reason=f"Order {order.status.value.lower()}")
    elif effect == Effect.ACCRUE_VENDOR_COST:
        ledger.accrue_vendor_cost(ctx, order)
    elif effect == Effect.CLOSE_QUOTE:
        quote_status = {
            OrderStatus.DECLINED: QuoteStatus.DECLINED,
            OrderStatus.QUOTE_EXPIRED: QuoteStatus.EXPIRED,
        }.get(order.status, QuoteStatus.CANCELLED)
        for quote in ctx.session.scalars(
            select(Quote).where(Quote.order_id == order.id, Quote.status == QuoteStatus.OPEN)
        ):
            quote.status = quote_status
            quote.responded_at = ctx.now
    elif effect == Effect.MARK_DELIVERED:
        order.delivered_at = ctx.now
        cod = next(iter(_payments(ctx, order, PaymentStatus.PENDING, PaymentMethod.COD)), None)
        if cod is not None:
            ledger.record_cod_collected(ctx, order, cod)
        try_complete(ctx, order)


def _payments(
    ctx: Ctx, order: Order, status: PaymentStatus, method: PaymentMethod | None = None
) -> list[Payment]:
    query = select(Payment).where(Payment.order_id == order.id, Payment.status == status)
    if method is not None:
        query = query.where(Payment.method == method)
    return list(ctx.session.scalars(query))


def refund_payment(ctx: Ctx, order: Order, payment: Payment, reason: str) -> Refund | None:
    """Queue a full refund of one paid digital payment (once per payment)."""
    if payment.method not in DIGITAL_METHODS or payment.status != PaymentStatus.PAID:
        return None
    if ctx.session.scalar(select(Refund.id).where(Refund.payment_id == payment.id)) is not None:
        return None
    refund = Refund(
        order_id=order.id,
        payment_id=payment.id,
        amount_paisa=payment.amount_paisa,
        status=RefundStatus.PENDING,
        reason=reason,
        created_at=ctx.now,
    )
    ctx.session.add(refund)
    ctx.session.flush()
    notifications.notify(
        ctx,
        order.user_id,
        NotificationKind.PAYMENT,
        *texts.refund_created(order, payment.amount_paisa),
        order=order,
    )
    enqueue = partial(ctx.services.tasks.enqueue, "process_refund", refund_id=str(refund.id))
    after_commit(ctx.session, enqueue)
    return refund


def create_refunds_for_paid(ctx: Ctx, order: Order, reason: str) -> list[Refund]:
    refunds = []
    for payment in _payments(ctx, order, PaymentStatus.PAID):
        refund = refund_payment(ctx, order, payment, reason)
        if refund is not None:
            refunds.append(refund)
    return refunds


def try_complete(ctx: Ctx, order: Order) -> bool:
    """COMPLETED needs delivery and settled payment (digital paid, or COD remitted)."""
    if order.status == OrderStatus.DELIVERED and order.payment_status == PaymentStatus.PAID:
        transition(ctx, order, OrderStatus.COMPLETED, actor=Actor.SYSTEM)
        order.completed_at = ctx.now
        return True
    return False


def can(order: Order, actor: Actor, target: OrderStatus) -> bool:
    rule = sm.find(order.type, order.status, target)
    return rule is not None and actor in rule.actors


# -- creation -----------------------------------------------------------------


def _require_can_order(user: User) -> None:
    if user.terms_accepted_at is None:
        raise conflict("terms-required", "Please accept the terms first")
    if user.phone_verified_at is None or user.phone_e164 is None:
        raise conflict("phone-required", "Please add and verify a mobile number first")


def _address(ctx: Ctx, user: User, address_id: uuid.UUID) -> tuple[Address, City]:
    address = ctx.session.get(Address, address_id)
    if address is None or address.user_id != user.id:
        raise not_found("Address")
    if not address.city.is_active:
        raise invalid("city-not-served", "We do not deliver to this city yet")
    return address, address.city


def _snapshot_shipping(order: Order, address: Address, city: City) -> None:
    order.ship_recipient_name = address.recipient_name
    order.ship_recipient_phone_e164 = address.recipient_phone_e164
    order.ship_city_id = city.id
    order.ship_city_name = city.name
    order.ship_zone_code = city.zone_code
    order.ship_area = address.area
    order.ship_street_address = address.street_address
    order.ship_landmark = address.landmark


def pricing_problem(error: PricingError) -> ProblemError:
    return invalid("pricing-error", error.message, error.message, pricing_code=error.code)


def check_cod_allowed(ctx: Ctx, method: PaymentMethod, total_paisa: int) -> None:
    if method != PaymentMethod.COD:
        return
    limit = load_settings(ctx).cod_max_order_value_paisa
    if limit is not None and total_paisa > limit:
        raise invalid(
            "cod-not-allowed",
            "Cash on delivery is not available for this amount",
            limit_paisa=limit,
        )


def check_method_enabled(ctx: Ctx, method: PaymentMethod) -> None:
    if method not in ctx.services.payments.enabled_methods():
        raise invalid("payment-method-unavailable", "This payment method is not available")


def check_expected_total(expected: int, breakdown: PriceBreakdown) -> None:
    if expected != breakdown.total_paisa:
        raise conflict(
            "price-mismatch",
            "The price has changed",
            total_paisa=breakdown.total_paisa,
            breakdown=breakdown.model_dump(mode="json"),
        )


def _history(ctx: Ctx, order: Order) -> None:
    ctx.session.add(
        OrderStatusHistory(
            order_id=order.id,
            from_status=None,
            to_status=order.status,
            actor=Actor.USER,
            actor_user_id=order.user_id,
            created_at=ctx.now,
        )
    )


def create_print_order(ctx: Ctx, user: User, body: PrintOrderCreate) -> Order:
    _require_can_order(user)
    upload = ctx.session.get(Upload, body.upload_id, with_for_update=True)
    if upload is None or upload.user_id != user.id:
        raise not_found("Upload")
    if upload.status != UploadStatus.VALID or upload.page_count is None:
        raise conflict("upload-not-ready", "The file has not passed its checks yet")
    if ctx.session.scalar(select(Order.id).where(Order.upload_id == upload.id)) is not None:
        raise conflict("upload-already-ordered", "This file is already part of an order")
    address, city = _address(ctx, user, body.address_id)
    check_method_enabled(ctx, body.payment_method)
    rules, version = pricing_store.active(ctx)
    try:
        breakdown = calculate(
            rules,
            version,
            PriceInput(
                pages=upload.page_count,
                paper=body.paper,
                binding=body.binding,
                copies=body.copies,
                zone=city.zone_code,
                payment_method=body.payment_method,
            ),
        )
    except PricingError as error:
        raise pricing_problem(error) from error
    check_cod_allowed(ctx, body.payment_method, breakdown.total_paisa)
    check_expected_total(body.expected_total_paisa, breakdown)

    digital = body.payment_method in DIGITAL_METHODS
    order = Order(
        code=new_order_code(ctx.session),
        user_id=user.id,
        type=OrderType.PRINT,
        status=OrderStatus.PENDING_PAYMENT if digital else OrderStatus.PLACED,
        upload_id=upload.id,
        pages=upload.page_count,
        paper=body.paper,
        binding=body.binding,
        copies=body.copies,
        payment_method=body.payment_method,
        payment_status=PaymentStatus.PENDING,
        pricing_config_version=version,
        price_breakdown=breakdown.model_dump(mode="json"),
        total_paisa=breakdown.total_paisa,
        created_at=ctx.now,
        updated_at=ctx.now,
    )
    _snapshot_shipping(order, address, city)
    ctx.session.add(order)
    ctx.session.flush()
    _history(ctx, order)
    start_payment(ctx, order)
    if order.status == OrderStatus.PLACED:
        notifications.notify_order_status(ctx, order)
    ctx.session.flush()
    return order


def create_source_order(ctx: Ctx, user: User, body: SourceOrderCreate) -> Order:
    _require_can_order(user)
    address, city = _address(ctx, user, body.address_id)
    rules, _ = pricing_store.active(ctx)
    if body.copies > rules.max_copies:
        raise invalid(
            "pricing-error",
            f"Choose at most {rules.max_copies} copies",
            pricing_code="INVALID_COPIES",
        )
    if city.zone_code not in rules.delivery_fees_paisa:
        raise invalid("city-not-served", "We do not deliver to this city yet")
    order = Order(
        code=new_order_code(ctx.session),
        user_id=user.id,
        type=OrderType.SOURCE,
        status=OrderStatus.REQUESTED,
        book_title=body.book_title,
        book_author=body.author,
        book_isbn=body.isbn,
        book_edition=body.edition,
        book_notes=body.notes,
        preferred_paper=body.preferred_paper,
        preferred_binding=body.preferred_binding,
        copies=body.copies,
        created_at=ctx.now,
        updated_at=ctx.now,
    )
    _snapshot_shipping(order, address, city)
    ctx.session.add(order)
    ctx.session.flush()
    _history(ctx, order)
    return order


# -- payments -------------------------------------------------------------------


def start_payment(ctx: Ctx, order: Order) -> Payment:
    """Create the payment for the order's total: COD waits for remittance,
    digital methods open the gateway's hosted checkout."""
    if order.payment_method is None or order.total_paisa is None:
        raise RuntimeError("start_payment needs a priced order with a payment method")
    method = order.payment_method
    if method == PaymentMethod.COD:
        payment = Payment(
            order_id=order.id,
            method=method,
            provider="cod",
            amount_paisa=order.total_paisa,
            status=PaymentStatus.PENDING,
            created_at=ctx.now,
        )
        ctx.session.add(payment)
        ctx.session.flush()
        return payment
    provider = ctx.services.payments.for_method(method)
    if provider is None:
        raise invalid("payment-method-unavailable", "This payment method is not available")
    payment = Payment(
        order_id=order.id,
        method=method,
        provider=provider.code,
        amount_paisa=order.total_paisa,
        status=PaymentStatus.PENDING,
        created_at=ctx.now,
    )
    ctx.session.add(payment)
    ctx.session.flush()
    try:
        session = provider.create_checkout(
            payment_id=payment.id,
            amount_paisa=payment.amount_paisa,
            order_code=order.code,
            return_url=f"kitaab://app/payment-result?order={order.id}",
        )
    except ProviderError as error:
        raise ProblemError(
            502,
            "payment-provider-error",
            "The payment service is not responding",
            error.public_message,
        ) from error
    payment.provider_ref = session.provider_ref
    payment.checkout_url = session.checkout_url
    order.payment_status = PaymentStatus.PENDING
    return payment


def retry_payment(ctx: Ctx, order: Order) -> Payment:
    awaiting = order.status == OrderStatus.PENDING_PAYMENT or (
        order.status == OrderStatus.ACCEPTED and order.payment_status != PaymentStatus.PAID
    )
    if not awaiting or order.payment_method not in DIGITAL_METHODS:
        raise conflict("payment-not-needed", "This order is not waiting for an online payment")
    for old in _payments(ctx, order, PaymentStatus.PENDING):
        old.status = PaymentStatus.FAILED
        old.failed_at = ctx.now
        old.failure_reason = "Replaced by a new attempt"
    return start_payment(ctx, order)


def ensure_owner(order: Order, user: User) -> None:
    if order.user_id != user.id:
        raise not_found("Order")


def ensure_vendor(order: Order, user: User) -> None:
    if user.vendor_id is None or order.vendor_id != user.vendor_id:
        raise not_found("Order")


def ensure_admin_reason(reason: str | None) -> str:
    if not reason or len(reason.strip()) < 3:
        raise invalid("reason-required", "Please give a reason")
    return reason.strip()


def forbid_unless(condition: bool, detail: str) -> None:
    if not condition:
        raise forbidden(detail)
