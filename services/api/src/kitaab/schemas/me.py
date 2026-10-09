import uuid
from datetime import datetime
from typing import Literal

from pydantic import Field

from kitaab.domain.enums import Role
from kitaab.schemas.common import Schema, ShortText


class MeOut(Schema):
    id: uuid.UUID
    role: Role
    full_name: str | None
    phone_e164: str | None
    email: str | None
    phone_verified: bool
    terms_accepted: bool = Field(description="False when the current terms version is not accepted")
    is_review_account: bool
    vendor_id: uuid.UUID | None
    created_at: datetime


class MeUpdate(Schema):
    full_name: ShortText


class TermsAccept(Schema):
    terms_version: str = Field(min_length=1, max_length=50)


class AccountDeletion(Schema):
    confirm: Literal["DELETE"]


class AccountDeletionResult(Schema):
    cancelled_order_codes: list[str]
    retained_order_codes: list[str] = Field(
        description="Orders past cancellation; their delivery details are removed once finished"
    )


class DeviceRegister(Schema):
    platform: Literal["android", "ios"]
    push_token: str = Field(min_length=10, max_length=4096)


class DeviceUnregister(Schema):
    push_token: str = Field(min_length=10, max_length=4096)
