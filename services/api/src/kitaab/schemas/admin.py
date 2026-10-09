import uuid
from datetime import datetime
from typing import Any

from pydantic import EmailStr, Field

from kitaab.domain.enums import (
    Actor,
    Binding,
    OrderStatus,
    OrderType,
    Paper,
    PaymentMethod,
    PaymentStatus,
    QuoteStatus,
    RefundStatus,
    Role,
    UploadStatus,
)
from kitaab.domain.pricing import PriceBreakdown, PricingRules
from kitaab.schemas.common import LongText, PageMeta, Paisa, Reason, Reference, Schema, ShortText
from kitaab.schemas.orders import OrderDetail, PaymentOut

# -- orders -------------------------------------------------------------------


class AdminOrderSummary(Schema):
    id: uuid.UUID
    code: str
    type: OrderType
    status: OrderStatus
    title: str
    customer_name: str | None
    customer_phone_masked: str
    city_name: str
    copies: int
    total_paisa: int | None
    payment_method: PaymentMethod | None
    payment_status: PaymentStatus | None
    vendor_name: str | None
    is_review_account: bool
    created_at: datetime
    updated_at: datetime


class AdminOrderPage(PageMeta):
    items: list[AdminOrderSummary]


class CustomerRef(Schema):
    id: uuid.UUID
    full_name: str | None
    phone_e164: str | None
    is_review_account: bool


class VendorRef(Schema):
    id: uuid.UUID
    name: str


class StatusHistoryOut(Schema):
    from_status: OrderStatus | None
    to_status: OrderStatus
    actor: Actor
    actor_name: str | None
    reason: str | None
    created_at: datetime


class AdminUploadInfo(Schema):
    id: uuid.UUID
    status: UploadStatus
    filename: str | None
    size_bytes: int
    page_count: int | None
    client_page_count: int | None
    sha256: str | None
    file_available: bool
    purged_at: datetime | None


class AdminQuoteOut(Schema):
    id: uuid.UUID
    status: QuoteStatus
    pages: int
    paper: Paper
    binding: Binding
    copies: int
    sourcing_cost_paisa: int
    calculated_goods_paisa: int
    goods_paisa: int
    override_reason: str | None
    breakdown: PriceBreakdown
    valid_until: datetime
    created_by_name: str | None
    created_at: datetime


class RefundOut(Schema):
    id: uuid.UUID
    order_id: uuid.UUID
    order_code: str
    amount_paisa: int
    status: RefundStatus
    reason: str
    reference: str | None
    created_at: datetime
    processed_at: datetime | None


class RefundPage(PageMeta):
    items: list[RefundOut]


class AdminOrderDetail(OrderDetail):
    customer: CustomerRef
    history: list[StatusHistoryOut]
    payments: list[PaymentOut]
    refunds: list[RefundOut]
    quotes: list[AdminQuoteOut]
    admin_upload: AdminUploadInfo | None
    vendor: VendorRef | None
    vendor_cost_paisa: int | None
    rejection_reason: str | None
    cancel_reason: str | None
    allowed_actions: list[str] = Field(
        description="Actions the admin can take now, e.g. start-verification, approve, reject"
    )


class ApproveAndAssign(Schema):
    vendor_id: uuid.UUID
    vendor_cost_paisa: Paisa


class ReasonIn(Schema):
    reason: Reason


class QuoteIn(Schema):
    pages: int = Field(ge=1)
    paper: Paper
    binding: Binding
    copies: int = Field(ge=1)
    sourcing_cost_paisa: Paisa
    goods_override_paisa: Paisa | None = None
    override_reason: Reason | None = None
    valid_hours: int | None = Field(default=None, ge=1, le=336)


class QuotePreview(Schema):
    breakdown: PriceBreakdown
    total_if_digital_paisa: int
    total_if_cod_paisa: int


class StartSourcing(Schema):
    vendor_id: uuid.UUID | None = None
    vendor_cost_paisa: Paisa | None = None


class DispatchIn(Schema):
    courier_code: str = Field(min_length=1, max_length=30)
    cn_number: str | None = Field(
        default=None, max_length=60, description="Enter only when the courier API is unavailable"
    )
    tracking_url: str | None = Field(default=None, max_length=500)


class RefundCreate(Schema):
    amount_paisa: int = Field(gt=0)
    reason: Reason


class RefundProcess(Schema):
    reference: Reference


class CourierOption(Schema):
    code: str
    name: str
    has_api: bool


# -- people ------------------------------------------------------------------


class VendorIn(Schema):
    name: ShortText
    contact_name: ShortText
    contact_phone: str
    email: EmailStr | None = None
    city_id: uuid.UUID | None = None
    address: LongText | None = None
    is_active: bool = True


class VendorOut(Schema):
    id: uuid.UUID
    name: str
    contact_name: str
    contact_phone_e164: str
    email: str | None
    city_id: uuid.UUID | None
    address: str | None
    is_active: bool
    created_at: datetime


class StaffUserCreate(Schema):
    email: EmailStr
    full_name: ShortText


class StaffUserOut(Schema):
    id: uuid.UUID
    role: Role
    email: str
    full_name: str | None
    vendor_id: uuid.UUID | None
    is_active: bool
    locked: bool
    last_login_at: datetime | None


class StaffUserCreated(Schema):
    user: StaffUserOut
    temporary_password: str = Field(description="Shown once; share it securely")
    totp_provisioning_uri: str | None = Field(
        description="Admins only: add to an authenticator app. Shown once."
    )


class StaffUserUpdate(Schema):
    is_active: bool | None = None
    unlock: bool = False


class CustomerSummary(Schema):
    id: uuid.UUID
    full_name: str | None
    phone_masked: str
    order_count: int
    is_review_account: bool
    deleted: bool
    created_at: datetime


class CustomerPage(PageMeta):
    items: list[CustomerSummary]


class CustomerDetail(Schema):
    id: uuid.UUID
    full_name: str | None
    phone_e164: str | None
    email: str | None
    google_linked: bool
    is_review_account: bool
    created_at: datetime
    deleted_at: datetime | None
    orders: list[AdminOrderSummary]


# -- configuration ------------------------------------------------------------


class PricingConfigVersion(Schema):
    version: int
    effective_from: datetime
    rules: PricingRules
    notes: str | None
    created_by_name: str | None
    created_at: datetime
    active: bool


class PricingConfigCreate(Schema):
    effective_from: datetime
    rules: PricingRules
    notes: LongText | None = None


class CityIn(Schema):
    name: ShortText
    province: ShortText
    zone_code: str = Field(min_length=1, max_length=20)
    is_active: bool = True
    sort_order: int = 0


class CityAdminOut(Schema):
    id: uuid.UUID
    name: str
    province: str
    zone_code: str
    is_active: bool
    sort_order: int


class AppSettings(Schema):
    cod_max_order_value_paisa: Paisa | None = Field(
        default=None, description="Orders above this must be prepaid; null turns the limit off"
    )
    quote_validity_hours: int = Field(default=48, ge=1, le=336)
    support_phone: str = ""
    support_whatsapp: str = ""
    support_email: str = ""
    support_hours: str = ""


class AuditLogOut(Schema):
    id: uuid.UUID
    actor_name: str | None
    actor_role: Role | None
    action: str
    entity_type: str
    entity_id: str | None
    details: dict[str, Any]
    created_at: datetime


class AuditLogPage(PageMeta):
    items: list[AuditLogOut]
