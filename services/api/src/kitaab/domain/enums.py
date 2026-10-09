"""Enumerations shared by models, schemas and business rules."""

from enum import StrEnum


class Role(StrEnum):
    CUSTOMER = "CUSTOMER"
    ADMIN = "ADMIN"
    VENDOR = "VENDOR"


class Actor(StrEnum):
    """Who performs an order transition."""

    USER = "USER"
    ADMIN = "ADMIN"
    VENDOR = "VENDOR"
    SYSTEM = "SYSTEM"


class OrderType(StrEnum):
    PRINT = "PRINT"
    SOURCE = "SOURCE"


class OrderStatus(StrEnum):
    # PRINT
    PENDING_PAYMENT = "PENDING_PAYMENT"
    PLACED = "PLACED"
    VERIFYING = "VERIFYING"
    ASSIGNED = "ASSIGNED"
    IN_PRINT = "IN_PRINT"
    REJECTED = "REJECTED"
    # SOURCE
    REQUESTED = "REQUESTED"
    QUOTED = "QUOTED"
    ACCEPTED = "ACCEPTED"
    SOURCING = "SOURCING"
    QUOTE_EXPIRED = "QUOTE_EXPIRED"
    DECLINED = "DECLINED"
    UNAVAILABLE = "UNAVAILABLE"
    # Shared
    READY_FOR_DISPATCH = "READY_FOR_DISPATCH"
    DISPATCHED = "DISPATCHED"
    DELIVERED = "DELIVERED"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"
    DELIVERY_FAILED = "DELIVERY_FAILED"


TERMINAL_STATUSES = frozenset(
    {
        OrderStatus.COMPLETED,
        OrderStatus.REJECTED,
        OrderStatus.CANCELLED,
        OrderStatus.QUOTE_EXPIRED,
        OrderStatus.DECLINED,
        OrderStatus.UNAVAILABLE,
        OrderStatus.DELIVERY_FAILED,
    }
)


class Paper(StrEnum):
    LOCAL_WHITE = "LOCAL_WHITE"
    IMPORTED_YELLOW = "IMPORTED_YELLOW"


class Binding(StrEnum):
    SOFTCOVER_PAPERBACK = "SOFTCOVER_PAPERBACK"
    PREMIUM_HARDCOVER = "PREMIUM_HARDCOVER"


class PaymentMethod(StrEnum):
    COD = "COD"
    EASYPAISA = "EASYPAISA"
    JAZZCASH = "JAZZCASH"
    CARD = "CARD"


DIGITAL_METHODS = frozenset({PaymentMethod.EASYPAISA, PaymentMethod.JAZZCASH, PaymentMethod.CARD})


class PaymentStatus(StrEnum):
    PENDING = "PENDING"
    PAID = "PAID"
    FAILED = "FAILED"
    REFUNDED = "REFUNDED"


class UploadStatus(StrEnum):
    AWAITING_PARTS = "AWAITING_PARTS"
    VALIDATING = "VALIDATING"
    VALID = "VALID"
    REJECTED = "REJECTED"
    ABORTED = "ABORTED"
    PURGED = "PURGED"


class UploadRejection(StrEnum):
    TOO_LARGE = "TOO_LARGE"
    SIZE_MISMATCH = "SIZE_MISMATCH"
    NOT_PDF = "NOT_PDF"
    CORRUPT = "CORRUPT"
    ENCRYPTED = "ENCRYPTED"
    NO_PAGES = "NO_PAGES"
    ACTIVE_CONTENT = "ACTIVE_CONTENT"
    MALWARE = "MALWARE"
    SCAN_FAILED = "SCAN_FAILED"


class QuoteStatus(StrEnum):
    OPEN = "OPEN"
    ACCEPTED = "ACCEPTED"
    DECLINED = "DECLINED"
    EXPIRED = "EXPIRED"
    CANCELLED = "CANCELLED"


class RefundStatus(StrEnum):
    PENDING = "PENDING"
    PROCESSED = "PROCESSED"


class LedgerEntryType(StrEnum):
    REVENUE = "REVENUE"
    COD_COLLECTED = "COD_COLLECTED"
    COD_REMITTED = "COD_REMITTED"
    VENDOR_COST_ACCRUED = "VENDOR_COST_ACCRUED"
    VENDOR_PAYOUT = "VENDOR_PAYOUT"
    REFUND = "REFUND"


class PayoutBatchStatus(StrEnum):
    OPEN = "OPEN"
    PAID = "PAID"


class NotificationKind(StrEnum):
    ORDER_STATUS = "ORDER_STATUS"
    QUOTE_READY = "QUOTE_READY"
    UPLOAD_RESULT = "UPLOAD_RESULT"
    PAYMENT = "PAYMENT"


class TimelineStep(StrEnum):
    PLACED = "PLACED"
    VERIFYING = "VERIFYING"  # shown as "Sourcing" for SOURCE orders
    PRINTING = "PRINTING"
    OUT_FOR_DELIVERY = "OUT_FOR_DELIVERY"
    COMPLETED = "COMPLETED"


class StepState(StrEnum):
    DONE = "DONE"
    CURRENT = "CURRENT"
    UPCOMING = "UPCOMING"
