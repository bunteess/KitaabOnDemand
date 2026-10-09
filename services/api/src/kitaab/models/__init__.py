"""SQLAlchemy models. Importing this package registers every table."""

from kitaab.models.audit import AuditLog
from kitaab.models.catalog import Address, AppSetting, City, PricingConfig, Vendor
from kitaab.models.ledger import LedgerEntry, PayoutBatch, PayoutBatchItem
from kitaab.models.notification import Notification
from kitaab.models.order import Order, OrderStatusHistory, Quote
from kitaab.models.payment import Payment, Refund, WebhookEvent
from kitaab.models.upload import Upload
from kitaab.models.user import Device, OtpChallenge, RefreshToken, User

__all__ = [
    "Address",
    "AppSetting",
    "AuditLog",
    "City",
    "Device",
    "LedgerEntry",
    "Notification",
    "Order",
    "OrderStatusHistory",
    "OtpChallenge",
    "Payment",
    "PayoutBatch",
    "PayoutBatchItem",
    "PricingConfig",
    "Quote",
    "RefreshToken",
    "Refund",
    "Upload",
    "User",
    "Vendor",
    "WebhookEvent",
]
