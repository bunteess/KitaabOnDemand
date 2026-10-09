from typing import Annotated, Literal

from pydantic import EmailStr, Field, StringConstraints

from kitaab.schemas.common import Schema
from kitaab.schemas.me import MeOut

OtpCode = Annotated[str, StringConstraints(pattern=r"^\d{6}$")]


class OtpRequest(Schema):
    phone: str = Field(examples=["0300 1234567"])


class OtpRequested(Schema):
    phone_e164: str
    expires_in_seconds: int
    resend_after_seconds: int


class OtpVerify(Schema):
    phone: str
    code: OtpCode


class GoogleSignIn(Schema):
    id_token: str = Field(min_length=10)


class RefreshRequest(Schema):
    refresh_token: str = Field(min_length=10)


class StaffLogin(Schema):
    email: EmailStr
    password: str = Field(min_length=1, max_length=200)
    totp_code: OtpCode | None = None


class TokenPair(Schema):
    access_token: str
    refresh_token: str
    token_type: Literal["bearer"] = "bearer"  # noqa: S105 (not a secret)
    expires_in: int = Field(description="Access token lifetime in seconds")
    user: MeOut
