import uuid
from datetime import datetime
from typing import Literal

from pydantic import Field

from kitaab.domain.enums import Binding, Paper, PaymentMethod
from kitaab.domain.pricing import PricingRules
from kitaab.schemas.common import LongText, Paisa, Schema, ShortText


class CityOut(Schema):
    id: uuid.UUID
    name: str
    province: str
    zone_code: str


class AddressIn(Schema):
    label: ShortText | None = None
    recipient_name: ShortText
    recipient_phone: str = Field(examples=["0300 1234567"])
    city_id: uuid.UUID
    area: ShortText
    street_address: LongText = Field(min_length=3)
    landmark: ShortText = Field(description="Nearest landmark, shown prominently to couriers")
    is_default: bool = False


class AddressOut(Schema):
    id: uuid.UUID
    label: str | None
    recipient_name: str
    recipient_phone_e164: str
    city: CityOut
    area: str
    street_address: str
    landmark: str
    is_default: bool


class SupportContact(Schema):
    phone: str
    whatsapp: str
    email: str
    hours: str


class PaymentMethodOption(Schema):
    method: PaymentMethod
    enabled: bool


class AppConfig(Schema):
    terms_version: str
    support: SupportContact
    payment_methods: list[PaymentMethodOption]
    max_upload_bytes: int
    upload_part_bytes: int
    cod_max_order_value_paisa: int | None = Field(
        description="Orders above this total must be paid digitally; null means no limit"
    )


class LegalDocument(Schema):
    doc: Literal["terms", "privacy", "copyright"]
    version: str
    title: str
    body: str = Field(description="Plain text with blank lines between paragraphs")


class PricingConfigOut(Schema):
    version: int
    effective_from: datetime
    rules: PricingRules


class PriceQuoteRequest(Schema):
    pages: int = Field(ge=1)
    paper: Paper
    binding: Binding
    copies: int = Field(default=1, ge=1)
    city_id: uuid.UUID
    payment_method: PaymentMethod | None = None


class CodLimit(Schema):
    cod_allowed: bool
    cod_max_order_value_paisa: Paisa | None
