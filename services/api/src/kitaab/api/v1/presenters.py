"""Turn models into the response schemas of the contract."""

from sqlalchemy import select

from kitaab.domain import quotes as quote_domain
from kitaab.domain.context import Ctx
from kitaab.domain.enums import (
    DIGITAL_METHODS,
    Actor,
    OrderStatus,
    OrderType,
    PaymentMethod,
    PaymentStatus,
    Role,
    UploadStatus,
)
from kitaab.domain.orders import service as orders
from kitaab.domain.orders import state_machine as sm
from kitaab.domain.orders.timeline import EXIT_STATUSES, build_timeline
from kitaab.domain.pricing import PriceBreakdown
from kitaab.models import (
    Address,
    City,
    Notification,
    Order,
    OrderStatusHistory,
    Payment,
    Quote,
    Refund,
    Upload,
    User,
    Vendor,
)
from kitaab.phone import mask_phone
from kitaab.schemas.admin import (
    AdminOrderDetail,
    AdminOrderSummary,
    AdminQuoteOut,
    AdminUploadInfo,
    CustomerRef,
    RefundOut,
    StaffUserOut,
    StatusHistoryOut,
    VendorOut,
    VendorRef,
)
from kitaab.schemas.catalog import AddressOut, CityOut
from kitaab.schemas.me import MeOut
from kitaab.schemas.notifications import NotificationOut
from kitaab.schemas.orders import (
    BookRequestOut,
    OrderDetail,
    OrderExit,
    OrderSummary,
    PaymentOut,
    QuoteOut,
    ShippingOut,
    TimelineEntry,
    TrackingOut,
)
from kitaab.schemas.uploads import UploadOut
from kitaab.schemas.vendor import VendorOrderDetail, VendorOrderSummary


def me_out(ctx: Ctx, user: User) -> MeOut:
    return MeOut(
        id=user.id,
        role=user.role,
        full_name=user.full_name,
        phone_e164=user.phone_e164,
        email=user.email,
        phone_verified=user.phone_verified_at is not None,
        terms_accepted=user.terms_version == ctx.services.settings.terms_version
        or (user.role != Role.CUSTOMER and user.terms_accepted_at is not None),
        is_review_account=user.is_review_account,
        vendor_id=user.vendor_id,
        created_at=user.created_at,
    )


def city_out(city: City) -> CityOut:
    return CityOut(id=city.id, name=city.name, province=city.province, zone_code=city.zone_code)


def address_out(address: Address) -> AddressOut:
    return AddressOut(
        id=address.id,
        label=address.label,
        recipient_name=address.recipient_name,
        recipient_phone_e164=address.recipient_phone_e164,
        city=city_out(address.city),
        area=address.area,
        street_address=address.street_address,
        landmark=address.landmark,
        is_default=address.is_default,
    )


def upload_out(upload: Upload, uploaded_parts: list[int] | None = None) -> UploadOut:
    messages = {
        "TOO_LARGE": "The file is larger than 150 MB",
        "SIZE_MISMATCH": "The uploaded file did not match its declared size",
        "NOT_PDF": "The file is not a PDF",
        "CORRUPT": "The file is damaged",
        "ENCRYPTED": "The file is password-protected",
        "NO_PAGES": "The file has no pages",
        "ACTIVE_CONTENT": "The file contains scripts or attachments",
        "MALWARE": "The file failed the safety check",
        "SCAN_FAILED": "The file could not be checked",
    }
    return UploadOut(
        id=upload.id,
        status=upload.status,
        filename=upload.filename,
        size_bytes=upload.size_bytes or upload.declared_size_bytes,
        page_count=upload.page_count
        if upload.status in (UploadStatus.VALID, UploadStatus.PURGED)
        else None,
        client_page_count=upload.client_page_count,
        rejection_code=upload.rejection_code,
        rejection_message=messages.get(upload.rejection_code.value)
        if upload.rejection_code
        else None,
        uploaded_parts=uploaded_parts or [],
        created_at=upload.created_at,
        validated_at=upload.validated_at,
    )


def _history(ctx: Ctx, order: Order) -> list[OrderStatusHistory]:
    return list(
        ctx.session.scalars(
            select(OrderStatusHistory)
            .where(OrderStatusHistory.order_id == order.id)
            .order_by(OrderStatusHistory.seq)
        )
    )


def _payments(ctx: Ctx, order: Order) -> list[Payment]:
    return list(
        ctx.session.scalars(
            select(Payment).where(Payment.order_id == order.id).order_by(Payment.created_at)
        )
    )


def payment_out(payment: Payment) -> PaymentOut:
    return PaymentOut(
        id=payment.id,
        method=payment.method,
        status=payment.status,
        amount_paisa=payment.amount_paisa,
        checkout_url=payment.checkout_url if payment.status == PaymentStatus.PENDING else None,
        paid_at=payment.paid_at,
    )


def _shipping(order: Order) -> ShippingOut:
    return ShippingOut(
        recipient_name=order.ship_recipient_name or "",
        recipient_phone_e164=order.ship_recipient_phone_e164 or "",
        city_name=order.ship_city_name,
        area=order.ship_area or "",
        street_address=order.ship_street_address or "",
        landmark=order.ship_landmark or "",
    )


def _quote_out(ctx: Ctx, quote: Quote) -> QuoteOut:
    digital, cod, cod_fee = quote_domain.totals(ctx, quote)
    breakdown = PriceBreakdown.model_validate(quote.breakdown)
    return QuoteOut(
        id=quote.id,
        status=quote.status,
        pages=quote.pages,
        paper=quote.paper,
        binding=quote.binding,
        copies=quote.copies,
        goods_paisa=quote.goods_paisa,
        delivery_paisa=breakdown.delivery_paisa,
        cod_fee_paisa=cod_fee,
        total_if_digital_paisa=digital,
        total_if_cod_paisa=cod,
        valid_until=quote.valid_until,
        created_at=quote.created_at,
    )


def _title(order: Order) -> str:
    if order.type == OrderType.SOURCE:
        return order.book_title or order.code
    return (order.upload.filename if order.upload else None) or order.code


def _awaiting_payment(order: Order) -> bool:
    return order.status == OrderStatus.PENDING_PAYMENT or (
        order.status == OrderStatus.ACCEPTED
        and order.payment_method in DIGITAL_METHODS
        and order.payment_status != PaymentStatus.PAID
    )


def _order_fields(ctx: Ctx, order: Order) -> dict[str, object]:
    history = _history(ctx, order)
    payments = _payments(ctx, order)
    latest_quote = ctx.session.scalar(
        select(Quote).where(Quote.order_id == order.id).order_by(Quote.created_at.desc()).limit(1)
    )
    timeline = build_timeline(
        order.type, order.status, [(h.to_status, h.created_at) for h in history]
    )
    exit_ = None
    if order.status in EXIT_STATUSES:
        exit_ = OrderExit(
            status=order.status, reason=order.exit_reason, at=order.terminal_at or order.updated_at
        )
    tracking = None
    if order.cn_number and order.dispatched_at:
        tracking = TrackingOut(
            courier_code=order.courier_code or "",
            courier_name=ctx.services.couriers.name_of(order.courier_code),
            cn_number=order.cn_number,
            tracking_url=order.tracking_url,
            dispatched_at=order.dispatched_at,
            last_status=order.courier_status,
        )
    book = None
    if order.type == OrderType.SOURCE:
        book = BookRequestOut(
            title=order.book_title or "",
            author=order.book_author,
            isbn=order.book_isbn,
            edition=order.book_edition,
            notes=order.book_notes,
            preferred_paper=order.preferred_paper,
            preferred_binding=order.preferred_binding,
        )
    return {
        "id": order.id,
        "code": order.code,
        "type": order.type,
        "status": order.status,
        "timeline": [TimelineEntry(step=s.step, state=s.state, at=s.at) for s in timeline],
        "exit": exit_,
        "awaiting_payment": _awaiting_payment(order),
        "pages": order.pages,
        "paper": order.paper,
        "binding": order.binding,
        "copies": order.copies,
        "upload": upload_out(order.upload) if order.upload else None,
        "book": book,
        "price": PriceBreakdown.model_validate(order.price_breakdown)
        if order.price_breakdown
        else None,
        "total_paisa": order.total_paisa,
        "payment": payment_out(payments[-1]) if payments else None,
        "shipping": _shipping(order),
        "quote": _quote_out(ctx, latest_quote) if latest_quote else None,
        "tracking": tracking,
        "can_cancel": orders.can(order, Actor.USER, OrderStatus.CANCELLED),
        "created_at": order.created_at,
        "updated_at": order.updated_at,
        "_history": history,
        "_payments": payments,
    }


def order_detail(ctx: Ctx, order: Order) -> OrderDetail:
    fields = _order_fields(ctx, order)
    return OrderDetail(**{k: v for k, v in fields.items() if not k.startswith("_")})


def order_summary(order: Order) -> OrderSummary:
    return OrderSummary(
        id=order.id,
        code=order.code,
        type=order.type,
        status=order.status,
        title=_title(order),
        total_paisa=order.total_paisa,
        needs_action=order.status == OrderStatus.QUOTED or _awaiting_payment(order),
        created_at=order.created_at,
        updated_at=order.updated_at,
    )


def admin_order_summary(order: Order) -> AdminOrderSummary:
    return AdminOrderSummary(
        id=order.id,
        code=order.code,
        type=order.type,
        status=order.status,
        title=_title(order),
        customer_name=order.user.full_name,
        customer_phone_masked=mask_phone(order.user.phone_e164),
        city_name=order.ship_city_name,
        copies=order.copies,
        total_paisa=order.total_paisa,
        payment_method=order.payment_method,
        payment_status=order.payment_status,
        vendor_name=order.vendor.name if order.vendor else None,
        is_review_account=order.user.is_review_account,
        created_at=order.created_at,
        updated_at=order.updated_at,
    )


def refund_out(refund: Refund, order_code: str) -> RefundOut:
    return RefundOut(
        id=refund.id,
        order_id=refund.order_id,
        order_code=order_code,
        amount_paisa=refund.amount_paisa,
        status=refund.status,
        reason=refund.reason,
        reference=refund.reference,
        created_at=refund.created_at,
        processed_at=refund.processed_at,
    )


def admin_actions(order: Order) -> list[str]:
    actions = sm.actions_for(order.type, order.status, Actor.ADMIN)
    payment_settled = (
        order.payment_status == PaymentStatus.PAID or order.payment_method == PaymentMethod.COD
    )
    if "start-sourcing" in actions and not payment_settled:
        actions.remove("start-sourcing")
    return actions


def _user_names(ctx: Ctx, ids: set[object]) -> dict[object, str | None]:
    if not ids:
        return {}
    return {
        u.id: u.full_name or u.email
        for u in ctx.session.scalars(select(User).where(User.id.in_(ids)))
    }


def admin_order_detail(ctx: Ctx, order: Order) -> AdminOrderDetail:
    fields = _order_fields(ctx, order)
    history: list[OrderStatusHistory] = fields.pop("_history")  # type: ignore[assignment]
    payments: list[Payment] = fields.pop("_payments")  # type: ignore[assignment]
    quote_rows = list(
        ctx.session.scalars(
            select(Quote).where(Quote.order_id == order.id).order_by(Quote.created_at)
        )
    )
    names = _user_names(
        ctx,
        {h.actor_user_id for h in history if h.actor_user_id}
        | {q.created_by_id for q in quote_rows if q.created_by_id},
    )
    refunds = ctx.session.scalars(
        select(Refund).where(Refund.order_id == order.id).order_by(Refund.created_at)
    )
    upload = order.upload
    return AdminOrderDetail(
        **fields,
        customer=CustomerRef(
            id=order.user.id,
            full_name=order.user.full_name,
            phone_e164=order.user.phone_e164,
            is_review_account=order.user.is_review_account,
        ),
        history=[
            StatusHistoryOut(
                from_status=h.from_status,
                to_status=h.to_status,
                actor=h.actor,
                actor_name=names.get(h.actor_user_id),
                reason=h.reason,
                created_at=h.created_at,
            )
            for h in history
        ],
        payments=[payment_out(p) for p in payments],
        refunds=[refund_out(r, order.code) for r in refunds],
        quotes=[
            AdminQuoteOut(
                id=q.id,
                status=q.status,
                pages=q.pages,
                paper=q.paper,
                binding=q.binding,
                copies=q.copies,
                sourcing_cost_paisa=q.sourcing_cost_paisa,
                calculated_goods_paisa=q.calculated_goods_paisa,
                goods_paisa=q.goods_paisa,
                override_reason=q.override_reason,
                breakdown=PriceBreakdown.model_validate(q.breakdown),
                valid_until=q.valid_until,
                created_by_name=names.get(q.created_by_id),
                created_at=q.created_at,
            )
            for q in quote_rows
        ],
        admin_upload=AdminUploadInfo(
            id=upload.id,
            status=upload.status,
            filename=upload.filename,
            size_bytes=upload.size_bytes or upload.declared_size_bytes,
            page_count=upload.page_count,
            client_page_count=upload.client_page_count,
            sha256=upload.sha256,
            file_available=upload.object_key is not None,
            purged_at=upload.purged_at,
        )
        if upload
        else None,
        vendor=VendorRef(id=order.vendor.id, name=order.vendor.name) if order.vendor else None,
        vendor_cost_paisa=order.vendor_cost_paisa,
        rejection_reason=order.exit_reason if order.status == OrderStatus.REJECTED else None,
        cancel_reason=order.exit_reason if order.status == OrderStatus.CANCELLED else None,
        allowed_actions=admin_actions(order),
    )


def _cod_amount(order: Order) -> int:
    if order.payment_method == PaymentMethod.COD and order.payment_status not in (
        PaymentStatus.REFUNDED,
    ):
        return order.total_paisa or 0
    return 0


def vendor_order_summary(order: Order) -> VendorOrderSummary:
    return VendorOrderSummary(
        id=order.id,
        code=order.code,
        type=order.type,
        status=order.status,
        title=_title(order),
        pages=order.pages,
        paper=order.paper,
        binding=order.binding,
        copies=order.copies,
        city_name=order.ship_city_name,
        cod_amount_paisa=_cod_amount(order),
        assigned_at=order.assigned_at,
    )


def vendor_order_detail(order: Order) -> VendorOrderDetail:
    actions = list(sm.actions_for(order.type, order.status, Actor.VENDOR))
    return VendorOrderDetail(
        **vendor_order_summary(order).model_dump(),
        shipping=_shipping(order),
        file_available=order.upload is not None and order.upload.object_key is not None,
        cn_number=order.cn_number,
        allowed_actions=actions,
    )


def notification_out(notification: Notification) -> NotificationOut:
    return NotificationOut(
        id=notification.id,
        kind=notification.kind,
        title=notification.title,
        body=notification.body,
        order_id=notification.order_id,
        read=notification.read_at is not None,
        created_at=notification.created_at,
    )


def vendor_out(vendor: Vendor) -> VendorOut:
    return VendorOut(
        id=vendor.id,
        name=vendor.name,
        contact_name=vendor.contact_name,
        contact_phone_e164=vendor.contact_phone_e164,
        email=vendor.email,
        city_id=vendor.city_id,
        address=vendor.address,
        is_active=vendor.is_active,
        created_at=vendor.created_at,
    )


def staff_out(ctx: Ctx, user: User) -> StaffUserOut:
    return StaffUserOut(
        id=user.id,
        role=user.role,
        email=user.email or "",
        full_name=user.full_name,
        vendor_id=user.vendor_id,
        is_active=user.is_active,
        locked=bool(user.locked_until and user.locked_until > ctx.now),
        last_login_at=user.last_login_at,
    )
