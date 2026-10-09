"""Every message a customer receives, in one place for later Urdu translation.
Short and plain: these appear as push notifications and SMS."""

from kitaab.domain.enums import OrderStatus, OrderType
from kitaab.models import Order
from kitaab.money import format_pkr

S = OrderStatus


def order_title(order: Order) -> str:
    if order.type == OrderType.SOURCE:
        return order.book_title or order.code
    return f"Order {order.code}"


def for_status(order: Order, *, courier_name: str = "") -> tuple[str, str] | None:
    """(title, body) for a status change, or None when the customer is not told."""
    name = order_title(order)
    reason = f" Reason: {order.exit_reason}" if order.exit_reason else ""
    return {
        S.PLACED: (
            "Order placed",
            f"We have your order {order.code}. We will check your file next.",
        ),
        S.QUOTED: ("Your price is ready", f"{name}: see the price and accept it in the app."),
        S.ASSIGNED: ("File approved", f"Order {order.code} has been sent to the printer."),
        S.IN_PRINT: ("Printing started", f"Order {order.code} is being printed."),
        S.SOURCING: ("Getting your book", f"We are getting {name} for you."),
        S.DISPATCHED: (
            "Out for delivery",
            f"Order {order.code} is on its way with {courier_name or 'the courier'}. "
            f"Tracking number {order.cn_number}.",
        ),
        S.DELIVERED: ("Delivered", f"Order {order.code} has been delivered. Thank you!"),
        S.REJECTED: ("File not accepted", f"We could not print order {order.code}.{reason}"),
        S.CANCELLED: ("Order cancelled", f"Order {order.code} has been cancelled.{reason}"),
        S.UNAVAILABLE: ("Book not available", f"We could not find {name}.{reason}"),
        S.QUOTE_EXPIRED: (
            "Price expired",
            f"The price for {name} has expired. You can request it again.",
        ),
        S.DELIVERY_FAILED: (
            "Delivery not completed",
            f"We could not deliver order {order.code}. We will contact you.",
        ),
    }.get(order.status)


# Status changes that also go by SMS when SMS_FALLBACK_ENABLED is on.
SMS_STATUSES = frozenset({S.QUOTED, S.DISPATCHED, S.DELIVERED, S.REJECTED, S.UNAVAILABLE})


def upload_valid(pages: int) -> tuple[str, str]:
    return "File ready", f"Your PDF has {pages} pages. You can now place your order."


def upload_rejected() -> tuple[str, str]:
    return "File not accepted", "We could not accept your PDF. Open the app to see why."


def payment_received(order: Order, amount_paisa: int) -> tuple[str, str]:
    return "Payment received", f"We received {format_pkr(amount_paisa)} for order {order.code}."


def payment_failed(order: Order) -> tuple[str, str]:
    return (
        "Payment not completed",
        f"The payment for order {order.code} did not go through. Try again in the app.",
    )


def refund_created(order: Order, amount_paisa: int) -> tuple[str, str]:
    return (
        "Refund on the way",
        f"We are refunding {format_pkr(amount_paisa)} for order {order.code}.",
    )


def otp_message(code: str) -> str:
    return f"{code} is your KitaabOnDemand code. It expires in 5 minutes. Do not share it."
