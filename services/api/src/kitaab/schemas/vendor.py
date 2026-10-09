import uuid
from datetime import datetime

from kitaab.domain.enums import Binding, OrderStatus, OrderType, Paper
from kitaab.schemas.common import PageMeta, Schema
from kitaab.schemas.orders import ShippingOut


class VendorOrderSummary(Schema):
    id: uuid.UUID
    code: str
    type: OrderType
    status: OrderStatus
    title: str
    pages: int | None
    paper: Paper | None
    binding: Binding | None
    copies: int
    city_name: str
    cod_amount_paisa: int
    assigned_at: datetime | None


class VendorOrderPage(PageMeta):
    items: list[VendorOrderSummary]


class VendorOrderDetail(VendorOrderSummary):
    shipping: ShippingOut
    file_available: bool
    cn_number: str | None
    allowed_actions: list[str]
