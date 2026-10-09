import pytest
from pydantic import SecretStr, ValidationError

from kitaab.config import Environment, Settings, production_problems

STRONG = "x" * 48


def production_settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "environment": Environment.PRODUCTION,
        "dev_tools_enabled": False,
        "review_mode_enabled": False,
        "jwt_secret": SecretStr(STRONG),
        "otp_pepper": SecretStr(STRONG),
        "mock_webhook_secret": SecretStr(STRONG),
        "data_encryption_key": SecretStr("cHJvZHVjdGlvbi1rZXktMDEyMzQ1Njc4OWFiY2RlZg=="),
        "database_url": "postgresql+psycopg://app:pw@db.internal:5432/kitaab",
        "sms_provider": "realsms",
        "payment_providers": ["easypaisa"],
        "courier_providers": ["trax"],
        "push_provider": "fcm",
        "web_origins": ["https://portal.example.pk"],
        "public_base_url": "https://api.example.pk",
        "clamav_enabled": True,
    }
    values.update(overrides)
    return Settings(**values)  # type: ignore[arg-type]


def test_safe_production_settings_boot() -> None:
    settings = production_settings()
    assert settings.is_production
    assert production_problems(settings) == []


@pytest.mark.parametrize(
    ("override", "message"),
    [
        ({"debug": True}, "DEBUG"),
        ({"dev_tools_enabled": True}, "DEV_TOOLS_ENABLED"),
        ({"review_mode_enabled": True}, "REVIEW_MODE_ENABLED"),
        ({"jwt_secret": SecretStr("dev-only-jwt-secret-change-me-0123456789abcdef")}, "JWT_SECRET"),
        ({"otp_pepper": SecretStr("short")}, "OTP_PEPPER"),
        ({"sms_provider": "mock"}, "SMS_PROVIDER"),
        ({"payment_providers": ["mock", "easypaisa"]}, "PAYMENT_PROVIDERS"),
        ({"courier_providers": ["mock"]}, "COURIER_PROVIDERS"),
        ({"push_provider": "fake"}, "PUSH_PROVIDER"),
        ({"web_origins": ["*"]}, "WEB_ORIGINS"),
        ({"public_base_url": "http://api.example.pk"}, "PUBLIC_BASE_URL"),
        ({"clamav_enabled": False}, "CLAMAV_ENABLED"),
    ],
)
def test_unsafe_production_settings_refuse_to_boot(
    override: dict[str, object], message: str
) -> None:
    with pytest.raises(ValidationError, match=message):
        production_settings(**override)


def test_default_encryption_key_and_database_are_rejected_in_production() -> None:
    with pytest.raises(ValidationError, match="DATA_ENCRYPTION_KEY"):
        production_settings(data_encryption_key=Settings().data_encryption_key)
    with pytest.raises(ValidationError, match="DATABASE_URL"):
        production_settings(database_url="postgresql+psycopg://kitaab:kitaab@localhost:5432/kitaab")


def test_review_mode_needs_explicit_override_and_new_otp_in_production() -> None:
    with pytest.raises(ValidationError, match="REVIEW_OTP"):
        production_settings(review_mode_enabled=True, allow_review_mode_in_production=True)
    settings = production_settings(
        review_mode_enabled=True,
        allow_review_mode_in_production=True,
        review_otp=SecretStr("482913"),
    )
    assert settings.review_mode_active


def test_review_mode_is_active_outside_production_without_override() -> None:
    assert Settings(review_mode_enabled=True).review_mode_active
    assert not Settings(review_mode_enabled=False).review_mode_active


def test_comma_separated_lists_are_split(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("WEB_ORIGINS", "https://a.example, https://b.example ,")
    monkeypatch.setenv("COURIER_PROVIDERS", "mock,trax")
    settings = Settings()
    assert settings.web_origins == ["https://a.example", "https://b.example"]
    assert settings.courier_providers == ["mock", "trax"]


def test_env_example_lists_every_setting() -> None:
    """services/api/.env.example documents every setting and nothing else."""
    from pathlib import Path

    example = Path(__file__).resolve().parents[1] / ".env.example"
    keys = {
        line.split("=", 1)[0].strip().lower()
        for line in example.read_text().splitlines()
        if "=" in line and not line.lstrip().startswith("#")
    }
    storage_credentials = {"aws_access_key_id", "aws_secret_access_key"}
    assert keys - storage_credentials == set(Settings.model_fields)


def test_env_example_values_are_valid_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    from pathlib import Path

    example = Path(__file__).resolve().parents[1] / ".env.example"
    for line in example.read_text().splitlines():
        if "=" in line and not line.lstrip().startswith("#"):
            key, value = line.split("=", 1)
            monkeypatch.setenv(key.strip(), value.split(" #")[0].strip())
    settings = Settings()
    assert settings.environment == "development"
    assert settings.s3_endpoint_url == "http://localhost:9000"
    assert settings.web_origins == ["http://localhost:5173", "http://localhost:8080"]
