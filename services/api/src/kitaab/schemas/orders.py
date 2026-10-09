import uuid
from datetime import datetime

from pydantic import Field

from kitaab.domain.enums import (
    Binding,
    OrderStatus,
    OrderType,
    Paper,
    PaymentMethod,
    PaymentStatus,
    QuoteStatus,
    StepState,
    TimelineStep,
)
from kitaab.domain.pricing import PriceBreakdown
from kitaab.schemas.common import LongText, PageMeta, Paisa, Schema, ShortText
from kitaab.schemas.uploads import UploadOut


class PrintOrderCreate(Schema):
    upload_id: uuid.UUID
    paper: Paper
    binding: Binding
    copies: int = Field(default=1, ge=1)
    address_id: uuid.UUID
    payment_method: PaymentMethod
    expected_total_paisa: Paisa = Field(
        description="Total shown to the customer; the order is refused if the server disagrees"
    )


class SourceOrderCreate(Schema):
    book_title: ShortText
    author: ShortText | None = None
    isbn: str | None = Field(default=None, max_length=20)
    edition: ShortText | None = None
    notes: LongText | None = None
    copies: int = Field(default=1, ge=1)
    preferred_paper: Paper | None = None
    preferred_binding: Binding | None = None
    address_id: uuid.UUID


class QuoteAccept(Schema):
    payment_method: PaymentMethod
    expected_total_paisa: Paisa


class CancelRequest(Schema):
    reason: str | None = Field(default=None, max_length=500)


class TimelineEntry(Schema):
    step: TimelineStep
    state: StepState
    at: datetime | None = Field(description="When the step was reached")


class OrderExit(Schema):
    status: OrderStatus
    reason: str | None
    at: datetime


class PaymentOut(Schema):
    id: uuid.UUID
    method: PaymentMethod
    status: PaymentStatus
    amount_paisa: int
    checkout_url: str | None = Field(description="Hosted payment page while payment is pending")
    paid_at: datetime | None


class ShippingOut(Schema):
    recipient_name: str
    recipient_phone_e164: str
    city_name: str
    area: str
    street_address: str
    landmark: str


class TrackingOut(Schema):
    courier_code: str
    courier_name: str
    cn_number: str
    tracking_url: str | None
    dispatched_at: datetime
    last_status: str | None


class QuoteOut(Schema):
    id: uuid.UUID
    status: QuoteStatus
    pages: int
    paper: Paper
    binding: Binding
    copies: int
    goods_paisa: int
    delivery_paisa: int
    cod_fee_paisa: int
    total_if_digital_paisa: int
    total_if_cod_paisa: int
    valid_until: datetime
    created_at: datetime


class BookRequestOut(Schema):
    title: str
    author: str | None
    isbn: str | None
    edition: str | None
    notes: str | None
    preferred_paper: Paper | None
    preferred_binding: Binding | None


class OrderSummary(Schema):
    id: uuid.UUID
    code: str
    type: OrderType
    status: OrderStatus
    title: str = Field(description="Book title or uploaded file name")
    total_paisa: int | None
    needs_action: bool = Field(description="A quote or payment is waiting for the customer")
    created_at: datetime
    updated_at: datetime


class OrderPage(PageMeta):
    items: list[OrderSummary]


class OrderDetail(Schema):
    id: uuid.UUID
    code: str
    type: OrderType
    status: OrderStatus
    timeline: list[TimelineEntry]
    exit: OrderExit | None
    awaiting_payment: bool
    pages: int | None
    paper: Paper | None
    binding: Binding | None
    copies: int
    upload: UploadOut | None
    book: BookRequestOut | None
    price: PriceBreakdown | None
    total_paisa: int | None
    payment: PaymentOut | None
    shipping: ShippingOut
    quote: QuoteOut | None
    tracking: TrackingOut | None
    can_cancel: bool
    created_at: datetime
    updated_at: datetime


class CheckoutSession(Schema):
    payment_id: uuid.UUID
    checkout_url: str
