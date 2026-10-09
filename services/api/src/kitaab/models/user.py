import uuid
from datetime import datetime

from sqlalchemy import Boolean, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from kitaab.db import Base
from kitaab.domain.enums import Role
from kitaab.models.base import (
    auto_updated,
    default_now,
    enum_column,
    required_timestamp,
    timestamp,
    uuid_pk,
)


class User(Base):
    """Customers (phone or Google), vendor staff and admins (email and password)."""

    __tablename__ = "users"

    id: Mapped[uuid.UUID] = uuid_pk()
    role: Mapped[Role] = mapped_column(enum_column(Role), index=True)
    full_name: Mapped[str | None] = mapped_column(String(120))
    phone_e164: Mapped[str | None] = mapped_column(String(16), unique=True)
    phone_verified_at: Mapped[datetime | None] = timestamp()
    email: Mapped[str | None] = mapped_column(String(254), unique=True)
    password_hash: Mapped[str | None] = mapped_column(String(200))
    totp_secret_enc: Mapped[str | None] = mapped_column(String(300))
    google_sub: Mapped[str | None] = mapped_column(String(64), unique=True)
    vendor_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("vendors.id"), index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_review_account: Mapped[bool] = mapped_column(Boolean, default=False)
    failed_login_count: Mapped[int] = mapped_column(Integer, default=0)
    locked_until: Mapped[datetime | None] = timestamp()
    terms_version: Mapped[str | None] = mapped_column(String(50))
    terms_accepted_at: Mapped[datetime | None] = timestamp()
    last_login_at: Mapped[datetime | None] = timestamp()
    deleted_at: Mapped[datetime | None] = timestamp()
    created_at: Mapped[datetime] = default_now()
    updated_at: Mapped[datetime] = auto_updated()


class OtpChallenge(Base):
    """A 6-digit code sent by SMS. Only an HMAC of the code is stored."""

    __tablename__ = "otp_challenges"

    id: Mapped[uuid.UUID] = uuid_pk()
    phone_e164: Mapped[str] = mapped_column(String(16), index=True)
    purpose: Mapped[str] = mapped_column(String(10))  # "login" or "link"
    user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    code_hash: Mapped[str] = mapped_column(String(64))
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    expires_at: Mapped[datetime] = required_timestamp()
    consumed_at: Mapped[datetime | None] = timestamp()
    ip_hash: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = default_now()


class RefreshToken(Base):
    """Rotating refresh tokens, grouped by family for reuse detection."""

    __tablename__ = "refresh_tokens"

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    family_id: Mapped[uuid.UUID] = mapped_column(index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    expires_at: Mapped[datetime] = required_timestamp()
    used_at: Mapped[datetime | None] = timestamp()
    revoked_at: Mapped[datetime | None] = timestamp()
    created_at: Mapped[datetime] = default_now()


class Device(Base):
    """A push token registered by the app."""

    __tablename__ = "devices"

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    platform: Mapped[str] = mapped_column(String(10))
    push_token: Mapped[str] = mapped_column(String(4096), unique=True)
    created_at: Mapped[datetime] = default_now()
    last_seen_at: Mapped[datetime] = default_now()
