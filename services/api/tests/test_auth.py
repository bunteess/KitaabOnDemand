"""Sign-in: phone OTP, Google, staff passwords with TOTP, token rotation."""

from datetime import timedelta

import pytest
from pydantic import SecretStr
from sqlalchemy import select

from kitaab.domain import auth
from kitaab.domain.enums import Role
from kitaab.models import OtpChallenge, RefreshToken, User
from kitaab.problems import ProblemError
from kitaab.security import totp
from support import ADMIN_PASSWORD, ADMIN_TOTP, Api

pytestmark = pytest.mark.integration

OTP_REQUEST = "/api/v1/auth/otp/request"
OTP_VERIFY = "/api/v1/auth/otp/verify"


def test_otp_sign_in_creates_a_customer_once(api: Api) -> None:
    first = api.customer("0300-1234567", terms=False)
    api.clock.advance(timedelta(minutes=2))
    again = api.customer("+92 300 1234567", terms=False)
    assert first.id == again.id
    assert first.phone == "+923001234567"
    me = api.get("/api/v1/me", again).json()
    assert me["role"] == "CUSTOMER"
    assert me["phone_verified"] is True
    assert me["terms_accepted"] is False


def test_sms_text_carries_the_code_and_logs_hide_the_number(
    api: Api, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level("INFO"):
        api.post(OTP_REQUEST, json={"phone": "03001234567"})
    to, text = api.sms.sent[-1]
    assert to == "+923001234567"
    assert "KitaabOnDemand" in text
    assert "+923001234567" not in caplog.text
    assert "3001234567" not in caplog.text


def test_codes_are_stored_hashed(api: Api) -> None:
    api.post(OTP_REQUEST, json={"phone": "03001234567"})
    code = api.last_code("+923001234567")
    with api.services.session() as session:
        challenge = session.scalars(select(OtpChallenge)).one()
    assert code not in challenge.code_hash
    assert len(challenge.code_hash) == 64


@pytest.mark.parametrize("phone", ["12345", "0423 1234567", "+44 7700 900123", "0300123456"])
def test_invalid_phone_numbers_are_refused(api: Api, phone: str) -> None:
    response = api.post(OTP_REQUEST, json={"phone": phone})
    assert response.status_code == 422
    assert response.json()["code"] == "invalid-phone"


def test_resend_cooldown(api: Api) -> None:
    assert api.post(OTP_REQUEST, json={"phone": "03001234567"}).status_code == 202
    again = api.post(OTP_REQUEST, json={"phone": "03001234567"})
    assert again.status_code == 429
    assert again.json()["code"] == "otp-cooldown"
    assert int(again.headers["Retry-After"]) == 60
    api.clock.advance(timedelta(seconds=61))
    assert api.post(OTP_REQUEST, json={"phone": "03001234567"}).status_code == 202


def test_new_code_replaces_the_old_one(api: Api) -> None:
    api.post(OTP_REQUEST, json={"phone": "03001234567"})
    old = api.last_code("+923001234567")
    api.clock.advance(timedelta(seconds=61))
    api.post(OTP_REQUEST, json={"phone": "03001234567"})
    new = api.last_code("+923001234567")
    if old != new:
        response = api.post(OTP_VERIFY, json={"phone": "03001234567", "code": old})
        assert response.status_code == 422
    assert api.post(OTP_VERIFY, json={"phone": "03001234567", "code": new}).status_code == 200


def test_daily_cap_per_phone(api: Api) -> None:
    cap = api.services.settings.otp_daily_cap_per_phone
    for _ in range(cap):
        assert api.post(OTP_REQUEST, json={"phone": "03001234567"}).status_code == 202
        api.clock.advance(timedelta(seconds=61))
    capped = api.post(OTP_REQUEST, json={"phone": "03001234567"})
    assert capped.status_code == 429
    assert capped.json()["code"] == "rate-limited"
    api.clock.advance(timedelta(days=1))
    assert api.post(OTP_REQUEST, json={"phone": "03001234567"}).status_code == 202


def test_requests_per_ip_are_limited(api: Api) -> None:
    limit = api.services.settings.otp_requests_per_ip_per_hour
    for n in range(limit):
        response = api.post(OTP_REQUEST, json={"phone": f"0301{n:07d}"})
        assert response.status_code == 202, response.text
    blocked = api.post(OTP_REQUEST, json={"phone": "03021234567"})
    assert blocked.status_code == 429
    assert "Retry-After" in blocked.headers


def test_code_expires(api: Api) -> None:
    api.post(OTP_REQUEST, json={"phone": "03001234567"})
    code = api.last_code("+923001234567")
    api.clock.advance(timedelta(seconds=api.services.settings.otp_ttl_seconds))
    response = api.post(OTP_VERIFY, json={"phone": "03001234567", "code": code})
    assert response.status_code == 422
    assert response.json()["code"] == "otp-expired"


def test_wrong_codes_lock_the_challenge(api: Api) -> None:
    api.post(OTP_REQUEST, json={"phone": "03001234567"})
    code = api.last_code("+923001234567")
    wrong = "000000" if code != "000000" else "111111"
    attempts = api.services.settings.otp_max_attempts
    for left in range(attempts - 1, -1, -1):
        response = api.post(OTP_VERIFY, json={"phone": "03001234567", "code": wrong})
        assert response.status_code == 422
        assert response.json()["extra"]["attempts_left"] == left
    assert response.json()["code"] == "otp-locked"
    # Even the right code no longer works.
    response = api.post(OTP_VERIFY, json={"phone": "03001234567", "code": code})
    assert response.status_code == 422


def test_a_code_works_once(api: Api) -> None:
    api.post(OTP_REQUEST, json={"phone": "03001234567"})
    code = api.last_code("+923001234567")
    assert api.post(OTP_VERIFY, json={"phone": "03001234567", "code": code}).status_code == 200
    assert api.post(OTP_VERIFY, json={"phone": "03001234567", "code": code}).status_code == 422


def test_review_mode_accepts_the_fixed_code(api: Api) -> None:
    api.services.settings = api.services.settings.model_copy(update={"review_mode_enabled": True})
    phone = api.services.settings.review_phone
    assert api.post(OTP_REQUEST, json={"phone": phone}).status_code == 202
    assert api.sms.sent == []
    assert api.post(OTP_VERIFY, json={"phone": phone, "code": "123456"}).status_code == 422
    response = api.post(OTP_VERIFY, json={"phone": phone, "code": "000000"})
    assert response.status_code == 200
    assert response.json()["user"]["is_review_account"] is True


def test_review_phone_is_ordinary_when_review_mode_is_off(api: Api) -> None:
    phone = api.services.settings.review_phone
    api.post(OTP_REQUEST, json={"phone": phone})
    assert len(api.sms.sent) == 1
    assert api.post(OTP_VERIFY, json={"phone": phone, "code": "000000"}).status_code == 422


# -- Google ---------------------------------------------------------------------------


def test_google_sign_in_then_phone_link(api: Api) -> None:
    response = api.post("/api/v1/auth/google", json={"id_token": "fake-google-12345"})
    assert response.status_code == 200
    data = response.json()
    assert data["user"]["phone_verified"] is False
    headers = {"Authorization": f"Bearer {data['access_token']}"}

    again = api.post("/api/v1/auth/google", json={"id_token": "fake-google-12345"})
    assert again.json()["user"]["id"] == data["user"]["id"]

    sent = api.client.post(
        "/api/v1/me/phone/request", headers=headers, json={"phone": "03111234567"}
    )
    assert sent.status_code == 202, sent.text
    code = api.last_code("+923111234567")
    linked = api.client.post(
        "/api/v1/me/phone/verify", headers=headers, json={"phone": "03111234567", "code": code}
    )
    assert linked.status_code == 200, linked.text
    assert linked.json()["phone_verified"] is True


def test_google_link_refuses_a_number_used_by_someone_else(api: Api) -> None:
    api.customer("03111234567")
    data = api.post("/api/v1/auth/google", json={"id_token": "fake-google-abc"}).json()
    headers = {"Authorization": f"Bearer {data['access_token']}"}
    api.clock.advance(timedelta(seconds=61))
    api.client.post("/api/v1/me/phone/request", headers=headers, json={"phone": "03111234567"})
    code = api.last_code("+923111234567")
    linked = api.client.post(
        "/api/v1/me/phone/verify", headers=headers, json={"phone": "03111234567", "code": code}
    )
    assert linked.status_code == 409
    assert linked.json()["code"] == "phone-in-use"


def test_a_login_code_cannot_link_a_phone(api: Api) -> None:
    data = api.post("/api/v1/auth/google", json={"id_token": "fake-google-xyz"}).json()
    headers = {"Authorization": f"Bearer {data['access_token']}"}
    api.post(OTP_REQUEST, json={"phone": "03111234567"})
    code = api.last_code("+923111234567")
    linked = api.client.post(
        "/api/v1/me/phone/verify", headers=headers, json={"phone": "03111234567", "code": code}
    )
    assert linked.status_code == 422


def test_bad_google_token(api: Api) -> None:
    response = api.post("/api/v1/auth/google", json={"id_token": "not-a-real-token"})
    assert response.status_code == 401
    assert response.json()["code"] == "invalid-id-token"


# -- staff ----------------------------------------------------------------------------


def test_admin_needs_password_and_totp(api: Api) -> None:
    api.admin()
    now = api.clock.now()
    no_code = api.staff_login("admin@example.com", ADMIN_PASSWORD, None)
    assert no_code.status_code == 401
    assert no_code.json()["code"] == "totp-required"
    bad_code = api.staff_login("admin@example.com", ADMIN_PASSWORD, "000000")
    assert bad_code.json()["code"] in ("totp-invalid", "invalid-credentials")
    good = api.staff_login("ADMIN@example.com", ADMIN_PASSWORD, totp.code_at(ADMIN_TOTP, now))
    assert good.status_code == 200
    assert good.json()["user"]["role"] == "ADMIN"


def test_old_totp_codes_are_refused(api: Api) -> None:
    api.admin()
    old = totp.code_at(ADMIN_TOTP, api.clock.now() - timedelta(minutes=5))
    response = api.staff_login("admin@example.com", ADMIN_PASSWORD, old)
    assert response.status_code == 401


def test_wrong_password_and_unknown_email_look_the_same(api: Api) -> None:
    api.admin()
    wrong = api.staff_login("admin@example.com", "nope", "123456")
    unknown = api.staff_login("nobody@example.com", "nope", "123456")
    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json()["code"] == unknown.json()["code"] == "invalid-credentials"


def test_lockout_after_repeated_failures(api: Api) -> None:
    api.admin()
    for _ in range(api.services.settings.staff_max_failed_logins):
        assert api.staff_login("admin@example.com", "wrong", None).status_code == 401
    code = totp.code_at(ADMIN_TOTP, api.clock.now())
    locked = api.staff_login("admin@example.com", ADMIN_PASSWORD, code)
    assert locked.status_code == 423
    assert locked.json()["code"] == "account-locked"
    api.clock.advance(timedelta(minutes=api.services.settings.staff_lockout_minutes, seconds=1))
    code = totp.code_at(ADMIN_TOTP, api.clock.now())
    assert api.staff_login("admin@example.com", ADMIN_PASSWORD, code).status_code == 200


def test_vendor_logs_in_without_totp(api: Api) -> None:
    vendor = api.vendor_user(api.vendor())
    me = api.get("/api/v1/me", vendor).json()
    assert me["role"] == "VENDOR"
    assert me["vendor_id"] == str(vendor.vendor_id)


def test_customers_cannot_use_staff_login(api: Api) -> None:
    api.customer("03001234567")
    response = api.staff_login("03001234567@example.com", "x", None)
    assert response.status_code == 401


def test_disabled_staff_cannot_sign_in(api: Api) -> None:
    admin = api.admin()
    with api.services.session() as session:
        user = session.get(User, admin.id)
        assert user is not None
        user.is_active = False
        session.commit()
    code = totp.code_at(ADMIN_TOTP, api.clock.now())
    assert api.staff_login("admin@example.com", ADMIN_PASSWORD, code).status_code == 401
    # Their access token stops working too.
    assert api.get("/api/v1/me", admin).status_code == 401


# -- tokens ---------------------------------------------------------------------------


def test_access_tokens_expire(api: Api) -> None:
    customer = api.customer()
    assert api.get("/api/v1/me", customer).status_code == 200
    api.clock.advance(timedelta(minutes=api.services.settings.access_token_ttl_minutes, seconds=1))
    response = api.get("/api/v1/me", customer)
    assert response.status_code == 401
    assert response.json()["code"] == "invalid-token"


def test_garbage_and_missing_tokens(api: Api) -> None:
    assert api.client.get("/api/v1/me").status_code == 401
    bad = api.client.get("/api/v1/me", headers={"Authorization": "Bearer not.a.token"})
    assert bad.status_code == 401
    basic = api.client.get("/api/v1/me", headers={"Authorization": "Basic abc"})
    assert basic.status_code == 401


def test_refresh_rotates_and_detects_reuse(api: Api) -> None:
    customer = api.customer()
    first = api.post("/api/v1/auth/refresh", json={"refresh_token": customer.refresh})
    assert first.status_code == 200
    rotated = first.json()["refresh_token"]
    assert rotated != customer.refresh

    reused = api.post("/api/v1/auth/refresh", json={"refresh_token": customer.refresh})
    assert reused.status_code == 401
    assert reused.json()["code"] == "refresh-token-reused"
    # The whole family is revoked, including the newest token.
    assert api.post("/api/v1/auth/refresh", json={"refresh_token": rotated}).status_code == 401


def test_refresh_tokens_expire(api: Api) -> None:
    customer = api.customer()
    api.clock.advance(timedelta(days=api.services.settings.refresh_token_ttl_days, seconds=1))
    response = api.post("/api/v1/auth/refresh", json={"refresh_token": customer.refresh})
    assert response.status_code == 401
    assert response.json()["code"] == "invalid-refresh-token"


def test_logout_revokes_the_session(api: Api) -> None:
    customer = api.customer()
    assert (
        api.post("/api/v1/auth/logout", json={"refresh_token": customer.refresh}).status_code == 204
    )
    response = api.post("/api/v1/auth/refresh", json={"refresh_token": customer.refresh})
    assert response.status_code == 401
    # Unknown tokens log out quietly.
    assert api.post("/api/v1/auth/logout", json={"refresh_token": "x" * 40}).status_code == 204


def test_refresh_tokens_are_stored_hashed(api: Api) -> None:
    customer = api.customer()
    with api.services.session() as session:
        hashes = session.scalars(select(RefreshToken.token_hash)).all()
    assert customer.refresh not in hashes
    assert len(hashes) == 1


def test_create_staff_refuses_duplicate_email(api: Api) -> None:
    from kitaab.domain import auth
    from kitaab.problems import ProblemError

    api.admin()
    ctx = api.ctx()
    with ctx.session, pytest.raises(ProblemError) as error:
        auth.create_staff(ctx, email="Admin@Example.com", full_name="Again", role=Role.ADMIN)
    assert error.value.code == "email-in-use"
    with pytest.raises(ValueError):
        auth.create_staff(ctx, email="c@example.com", full_name="C", role=Role.CUSTOMER)


def test_reset_staff_login_issues_new_credentials(api: Api) -> None:
    admin = api.admin()
    for _ in range(api.services.settings.staff_max_failed_logins):
        api.staff_login("admin@example.com", "wrong", None)
    ctx = api.ctx()
    with ctx.session:
        new = auth.reset_staff_login(ctx, "ADMIN@example.com")
        ctx.session.commit()
    assert new.totp_secret is not None
    assert new.totp_secret != ADMIN_TOTP
    assert new.totp_uri is not None
    assert new.totp_uri.startswith("otpauth://totp/")
    now = api.clock.now()
    old_code = totp.code_at(ADMIN_TOTP, now)
    assert api.staff_login("admin@example.com", ADMIN_PASSWORD, old_code).status_code == 401
    assert api.staff_login("admin@example.com", new.temporary_password, old_code).status_code == 401
    new_code = totp.code_at(new.totp_secret, now)
    # The lockout is cleared and the new password and authenticator work.
    good = api.staff_login("admin@example.com", new.temporary_password, new_code)
    assert good.status_code == 200
    # Every earlier session was signed out.
    stale = api.post("/api/v1/auth/refresh", json={"refresh_token": admin.refresh})
    assert stale.status_code == 401

    vendor = api.vendor_user(api.vendor())
    with ctx.session:
        user = ctx.session.get(User, vendor.id)
        assert user is not None
        assert user.email is not None
        reset = auth.reset_staff_login(ctx, user.email)
        assert reset.totp_secret is None
        with pytest.raises(ProblemError):
            auth.reset_staff_login(ctx, "nobody@example.com")


def test_reencrypt_totp_secrets_moves_to_the_new_key(
    api: Api, monkeypatch: pytest.MonkeyPatch
) -> None:
    api.admin()
    settings = api.services.settings
    old_key = settings.data_encryption_key.get_secret_value()
    monkeypatch.setattr(settings, "data_encryption_key", SecretStr("a-brand-new-key-" + "x" * 32))
    code = totp.code_at(ADMIN_TOTP, api.clock.now())
    # With only the new key configured, the old secret cannot be read.
    assert api.staff_login("admin@example.com", ADMIN_PASSWORD, code).status_code == 403
    ctx = api.ctx()
    with ctx.session:
        assert auth.reencrypt_totp_secrets(ctx, old_key) == (1, 0)
        ctx.session.commit()
    assert api.staff_login("admin@example.com", ADMIN_PASSWORD, code).status_code == 200
    with ctx.session:
        assert auth.reencrypt_totp_secrets(ctx, old_key) == (0, 1)
    # A wrong old key and a wrong new key: refuse, and change nothing.
    monkeypatch.setattr(settings, "data_encryption_key", SecretStr("a-third-key-" + "y" * 32))
    with ctx.session, pytest.raises(ValueError, match="neither key"):
        auth.reencrypt_totp_secrets(ctx, "some-unrelated-key")
    monkeypatch.setattr(settings, "data_encryption_key", SecretStr("a-brand-new-key-" + "x" * 32))
    assert api.staff_login("admin@example.com", ADMIN_PASSWORD, code).status_code == 200
