"""Application settings, read from environment variables and validated at startup.

With ENVIRONMENT=production the app refuses to start on unsafe settings
(debug, dev tools, mock providers, default secrets, review mode without the
explicit override). See docs/DECISIONS.md D-020 for the review mode rule.
"""

from enum import StrEnum
from functools import lru_cache
from typing import Annotated

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

MB = 1024 * 1024

CommaList = Annotated[list[str], NoDecode]


class Environment(StrEnum):
    DEVELOPMENT = "development"
    TEST = "test"
    STAGING = "staging"
    PRODUCTION = "production"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore", case_sensitive=False)

    environment: Environment = Environment.DEVELOPMENT
    debug: bool = False
    log_level: str = "INFO"
    sentry_dsn: str | None = None

    database_url: str = "postgresql+psycopg://kitaab:kitaab@localhost:5432/kitaab"
    redis_url: str = "redis://localhost:6379/0"

    # Secrets
    jwt_secret: SecretStr = SecretStr("dev-only-jwt-secret-change-me-0123456789abcdef")
    otp_pepper: SecretStr = SecretStr("dev-only-otp-pepper-change-me")
    # Fernet key (32 url-safe base64 bytes) used to encrypt TOTP secrets at rest.
    data_encryption_key: SecretStr = SecretStr("ZGV2LW9ubHkta2V5LWNoYW5nZS1tZS0wMTIzNDU2Nzg=")
    mock_webhook_secret: SecretStr = SecretStr("dev-only-mock-webhook-secret")

    # Tokens
    access_token_ttl_minutes: int = 15
    refresh_token_ttl_days: int = 30

    # URLs
    public_base_url: str = "http://localhost:8000"
    internal_api_url: str = "http://localhost:8000"
    web_origins: CommaList = Field(default_factory=lambda: ["http://localhost:5173"])

    # Object storage. Credentials come from the standard AWS environment
    # variables or an instance role, so they are not settings here.
    s3_bucket: str = "kitaab-dev"
    s3_region: str = "ap-south-1"
    s3_endpoint_url: str | None = None
    s3_public_endpoint_url: str | None = None

    # Uploads and files
    max_upload_bytes: int = 150 * MB
    upload_part_bytes: int = 8 * MB
    upload_url_ttl_seconds: int = 24 * 3600
    download_url_ttl_seconds: int = 300
    unattached_upload_ttl_hours: int = 24
    purge_days: int = 7
    purge_dry_run: bool = False
    clamav_enabled: bool = False
    clamav_host: str = "localhost"
    clamav_port: int = 3310

    # Orders
    pending_payment_ttl_hours: int = 24
    quote_validity_hours_default: int = 48

    # Customer OTP
    otp_ttl_seconds: int = 300
    otp_max_attempts: int = 5
    otp_resend_cooldown_seconds: int = 60
    otp_daily_cap_per_phone: int = 10
    otp_requests_per_ip_per_hour: int = 30

    # Staff login
    staff_max_failed_logins: int = 5
    staff_lockout_minutes: int = 15

    # Store reviewer demo account (docs/DECISIONS.md D-020)
    review_mode_enabled: bool = False
    allow_review_mode_in_production: bool = False
    review_phone: str = "+923000000000"
    review_otp: SecretStr = SecretStr("000000")

    # Development helpers: clock offset, SMS outbox, mock provider controls.
    dev_tools_enabled: bool = False

    # Providers (docs/INTEGRATIONS.md)
    sms_provider: str = "mock"
    sms_fallback_enabled: bool = False
    payment_providers: CommaList = Field(default_factory=lambda: ["mock"])
    courier_providers: CommaList = Field(default_factory=lambda: ["mock"])
    push_provider: str = "fake"
    fcm_credentials_file: str | None = None
    google_oauth_client_ids: CommaList = Field(default_factory=list)
    mock_provider_failure_rate: float = 0.0
    mock_provider_latency_ms: int = 0

    # Legal
    terms_version: str = "placeholder-2026-10"

    @field_validator(
        "web_origins",
        "payment_providers",
        "courier_providers",
        "google_oauth_client_ids",
        mode="before",
    )
    @classmethod
    def _split_commas(cls, value: object) -> object:
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value

    @property
    def is_production(self) -> bool:
        return self.environment == Environment.PRODUCTION

    @property
    def review_mode_active(self) -> bool:
        return self.review_mode_enabled and (
            not self.is_production or self.allow_review_mode_in_production
        )

    @model_validator(mode="after")
    def _check_production_safety(self) -> "Settings":
        if self.is_production:
            problems = production_problems(self)
            if problems:
                raise ValueError(
                    "Refusing to start with unsafe production settings: " + "; ".join(problems)
                )
        return self


def _is_weak_secret(value: SecretStr, min_length: int = 32) -> bool:
    raw = value.get_secret_value()
    return len(raw) < min_length or "dev-only" in raw or "change-me" in raw


def production_problems(settings: Settings) -> list[str]:
    """Return every reason the settings are unsafe for production."""
    problems: list[str] = []
    if settings.debug:
        problems.append("DEBUG must be false")
    if settings.dev_tools_enabled:
        problems.append("DEV_TOOLS_ENABLED must be false")
    if settings.review_mode_enabled and not settings.allow_review_mode_in_production:
        problems.append(
            "REVIEW_MODE_ENABLED is on; set ALLOW_REVIEW_MODE_IN_PRODUCTION=true only for "
            "the store review window"
        )
    if settings.review_mode_enabled and settings.review_otp.get_secret_value() == "000000":
        problems.append("REVIEW_OTP must be changed from the default")
    for name in ("jwt_secret", "otp_pepper", "mock_webhook_secret"):
        if _is_weak_secret(getattr(settings, name)):
            problems.append(f"{name.upper()} is missing, too short or a development default")
    if "ZGV2LW9ubHk" in settings.data_encryption_key.get_secret_value():
        problems.append("DATA_ENCRYPTION_KEY is the development default")
    if settings.sms_provider == "mock":
        problems.append("SMS_PROVIDER must not be mock")
    if "mock" in settings.payment_providers:
        problems.append("PAYMENT_PROVIDERS must not include mock")
    if "mock" in settings.courier_providers:
        problems.append("COURIER_PROVIDERS must not include mock")
    if settings.push_provider == "fake":
        problems.append("PUSH_PROVIDER must not be fake")
    if not settings.web_origins or "*" in settings.web_origins:
        problems.append("WEB_ORIGINS must list explicit origins")
    if not settings.public_base_url.startswith("https://"):
        problems.append("PUBLIC_BASE_URL must use https")
    if not settings.clamav_enabled:
        problems.append("CLAMAV_ENABLED must be true")
    if settings.database_url.endswith("kitaab:kitaab@localhost:5432/kitaab"):
        problems.append("DATABASE_URL is the development default")
    return problems


@lru_cache
def get_settings() -> Settings:
    return Settings()
