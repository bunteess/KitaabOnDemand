import datetime as dt
import uuid

from pydantic import Field

from kitaab.domain.enums import PaymentMethod, PayoutBatchStatus
from kitaab.schemas.common import Reference, Schema


class DailyRevenueRow(Schema):
    date: dt.date = Field(description="Calendar day in Pakistan time")
    payment_method: PaymentMethod
    orders: int
    gross_paisa: int
    refunds_paisa: int
    net_paisa: int


class DailyRevenueReport(Schema):
    from_date: dt.date
    to_date: dt.date
    rows: list[DailyRevenueRow]
    total_gross_paisa: int
    total_refunds_paisa: int
    total_net_paisa: int


class CodPendingOrder(Schema):
    order_id: uuid.UUID
    order_code: str
    cn_number: str | None
    amount_paisa: int
    delivered_at: dt.datetime


class CodPendingGroup(Schema):
    courier_code: str
    courier_name: str
    total_paisa: int
    orders: list[CodPendingOrder]


class CodRemittanceCreate(Schema):
    courier_code: str
    order_ids: list[uuid.UUID] = Field(min_length=1)
    reference: Reference


class CodRemittanceResult(Schema):
    courier_code: str
    orders: int
    total_paisa: int
    reference: str


class VendorPayoutRow(Schema):
    vendor_id: uuid.UUID
    vendor_name: str
    accrued_paisa: int
    paid_paisa: int
    in_open_batches_paisa: int
    owed_paisa: int = Field(description="Accrued minus paid")


class PayoutBatchCreate(Schema):
    vendor_id: uuid.UUID


class PayoutBatchItem(Schema):
    order_id: uuid.UUID
    order_code: str
    amount_paisa: int


class PayoutBatchOut(Schema):
    id: uuid.UUID
    vendor_id: uuid.UUID
    vendor_name: str
    status: PayoutBatchStatus
    total_paisa: int
    reference: str | None
    items: list[PayoutBatchItem]
    created_at: dt.datetime
    paid_at: dt.datetime | None


class PayoutBatchPay(Schema):
    reference: Reference
