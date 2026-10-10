"""Sign-in (brief section 3.4).

Customers: phone OTP, or a Google ID token followed by phone verification
before the first order. Staff: email and password (argon2), lockout after
repeated failures, TOTP required for admins. Everyone gets a 15-minute access
token and a rotating refresh token with reuse detection.
"""

import hashlib
import hmac
import logging
import secrets
import uuid
from dataclasses import dataclass
from datetime import timedelta

from sqlalchemy import func, select, update

from kitaab.domain import notification_texts as texts
from kitaab.domain.context import Ctx
from kitaab.domain.enums import Role
from kitaab.models import OtpChallenge, RefreshToken, User
from kitaab.phone import InvalidPhoneError, mask_phone, normalize_pk_mobile
from kitaab.problems import ProblemError, conflict, invalid, not_found
from kitaab.providers.errors import ProviderError
from kitaab.providers.id_tokens import InvalidIdToken
from kitaab.security import passwords, totp
from kitaab.security.ratelimit import Limit
from kitaab.security.tokens import hash_token, make_access_token, new_refresh_token
from kitaab.tx import after_commit

log = logging.getLogger(__name__)

PURPOSE_LOGIN = "login"
PURPOSE_LINK = "link"
STAFF_LOGINS_PER_IP = Limit(30, 900)
OTP_VERIFIES_PER_IP = Limit(60, 3600)


@dataclass(frozen=True)
class OtpSent:
    phone_e164: str
    expires_in_seconds: int
    resend_after_seconds: int


@dataclass(frozen=True)
class Tokens:
    access_token: str
    refresh_token: str
    expires_in: int
    user: User


def rate_limited(
    retry_after: int, title: str = "Too many attempts. Please wait and try again."
) -> ProblemError:
    return ProblemError(
        429,
        "rate-limited",
        title,
        headers={"Retry-After": str(retry_after)},
        extra={"retry_after_seconds": retry_after},
    )


def hash_ip(ip: str | None, pepper: str) -> str | None:
    return hmac.new(pepper.encode(), ip.encode(), hashlib.sha256).hexdigest() if ip else None


def _code_hash(pepper: str, phone: str, code: str) -> str:
    return hmac.new(pepper.encode(), f"{phone}:{code}".encode(), hashlib.sha256).hexdigest()


def normalize_phone(raw: str) -> str:
    try:
        return normalize_pk_mobile(raw)
    except InvalidPhoneError as error:
        raise invalid(
            "invalid-phone", "Enter a Pakistani mobile number, for example 0300 1234567"
        ) from error


def is_review_phone(ctx: Ctx, phone: str) -> bool:
    settings = ctx.services.settings
    return settings.review_mode_active and phone == normalize_pk_mobile(settings.review_phone)


# -- OTP ---------------------------------------------------------------------------


def request_otp(
    ctx: Ctx,
    raw_phone: str,
    ip: str | None,
    *,
    purpose: str = PURPOSE_LOGIN,
    user: User | None = None,
) -> OtpSent:
    settings = ctx.services.settings
    phone = normalize_phone(raw_phone)
    if is_review_phone(ctx, phone):
        # Store reviewers cannot receive Pakistani SMS: the code is fixed (REVIEW_OTP).
        return OtpSent(phone, settings.otp_ttl_seconds, settings.otp_resend_cooldown_seconds)

    pepper = settings.otp_pepper.get_secret_value()
    ip_hash = hash_ip(ip, pepper)
    if ip_hash:
        retry = ctx.services.rate_limiter.hit(
            f"otp:ip:{ip_hash}", Limit(settings.otp_requests_per_ip_per_hour, 3600)
        )
        if retry is not None:
            raise rate_limited(retry)

    last = ctx.session.scalar(
        select(OtpChallenge)
        .where(OtpChallenge.phone_e164 == phone)
        .order_by(OtpChallenge.created_at.desc())
        .limit(1)
    )
    if last is not None:
        wait = settings.otp_resend_cooldown_seconds - int(
            (ctx.now - last.created_at).total_seconds()
        )
        if wait > 0:
            raise ProblemError(
                429,
                "otp-cooldown",
                "Please wait before asking for a new code",
                headers={"Retry-After": str(wait)},
                extra={"retry_after_seconds": wait},
            )
    sent_today = ctx.session.scalar(
        select(func.count())
        .select_from(OtpChallenge)
        .where(
            OtpChallenge.phone_e164 == phone, OtpChallenge.created_at > ctx.now - timedelta(days=1)
        )
    )
    if (sent_today or 0) >= settings.otp_daily_cap_per_phone:
        raise rate_limited(3600, "Too many codes requested today. Please try again tomorrow.")

    code = f"{secrets.randbelow(1_000_000):06d}"
    # Older unused codes for this phone stop working once a new one is sent.
    ctx.session.execute(
        update(OtpChallenge)
        .where(OtpChallenge.phone_e164 == phone, OtpChallenge.consumed_at.is_(None))
        .values(consumed_at=ctx.now)
    )
    ctx.session.add(
        OtpChallenge(
            phone_e164=phone,
            purpose=purpose,
            user_id=user.id if user else None,
            code_hash=_code_hash(pepper, phone, code),
            expires_at=ctx.now + timedelta(seconds=settings.otp_ttl_seconds),
            ip_hash=ip_hash,
            created_at=ctx.now,
        )
    )
    ctx.session.flush()
    sms = ctx.services.sms
    message = texts.otp_message(code)

    def send() -> None:
        try:
            sms.send(phone, message)
        except ProviderError:
            log.error("otp sms failed", extra={"phone": mask_phone(phone)})

    after_commit(ctx.session, send)
    return OtpSent(phone, settings.otp_ttl_seconds, settings.otp_resend_cooldown_seconds)


def verify_otp(
    ctx: Ctx, raw_phone: str, code: str, ip: str | None, *, purpose: str = PURPOSE_LOGIN
) -> str:
    """Checks the code and returns the verified E.164 phone."""
    settings = ctx.services.settings
    phone = normalize_phone(raw_phone)
    if is_review_phone(ctx, phone):
        if hmac.compare_digest(code, settings.review_otp.get_secret_value()):
            return phone
        raise invalid("otp-invalid", "Wrong code", attempts_left=settings.otp_max_attempts)

    pepper = settings.otp_pepper.get_secret_value()
    ip_hash = hash_ip(ip, pepper)
    if ip_hash:
        retry = ctx.services.rate_limiter.hit(f"otp-verify:ip:{ip_hash}", OTP_VERIFIES_PER_IP)
        if retry is not None:
            raise rate_limited(retry)
    challenge = ctx.session.scalar(
        select(OtpChallenge)
        .where(
            OtpChallenge.phone_e164 == phone,
            OtpChallenge.purpose == purpose,
            OtpChallenge.consumed_at.is_(None),
        )
        .order_by(OtpChallenge.created_at.desc())
        .limit(1)
        .with_for_update()
    )
    if challenge is None or challenge.expires_at <= ctx.now:
        raise invalid("otp-expired", "This code has expired. Ask for a new one.")
    if challenge.attempts >= settings.otp_max_attempts:
        raise invalid("otp-locked", "Too many wrong codes. Ask for a new one.")
    challenge.attempts += 1
    if not hmac.compare_digest(challenge.code_hash, _code_hash(pepper, phone, code)):
        left = settings.otp_max_attempts - challenge.attempts
        if left <= 0:
            challenge.consumed_at = ctx.now
        # Commit the attempt count even though the request fails.
        ctx.session.commit()
        raise invalid(
            "otp-invalid" if left > 0 else "otp-locked", "Wrong code", attempts_left=max(left, 0)
        )
    challenge.consumed_at = ctx.now
    return phone


def customer_for_phone(ctx: Ctx, phone: str) -> User:
    user = ctx.session.scalar(
        select(User).where(User.phone_e164 == phone, User.deleted_at.is_(None))
    )
    if user is None:
        user = User(
            role=Role.CUSTOMER,
            phone_e164=phone,
            phone_verified_at=ctx.now,
            is_review_account=is_review_phone(ctx, phone),
            created_at=ctx.now,
            updated_at=ctx.now,
        )
        ctx.session.add(user)
        ctx.session.flush()
    elif user.role != Role.CUSTOMER:
        raise conflict("not-a-customer", "This number belongs to a staff account")
    if not user.is_active:
        raise ProblemError(403, "account-disabled", "This account is disabled. Contact support.")
    user.phone_verified_at = user.phone_verified_at or ctx.now
    user.last_login_at = ctx.now
    return user


def link_phone(ctx: Ctx, user: User, phone: str) -> User:
    other = ctx.session.scalar(
        select(User).where(User.phone_e164 == phone, User.id != user.id, User.deleted_at.is_(None))
    )
    if other is not None:
        raise conflict("phone-in-use", "This number is already used by another account")
    user.phone_e164 = phone
    user.phone_verified_at = ctx.now
    return user


def sign_in_with_google(ctx: Ctx, id_token: str) -> User:
    try:
        identity = ctx.services.id_tokens.verify(id_token)
    except InvalidIdToken as error:
        raise ProblemError(
            401, "invalid-id-token", "Google sign-in could not be verified"
        ) from error
    user = ctx.session.scalar(
        select(User).where(User.google_sub == identity.subject, User.deleted_at.is_(None))
    )
    if user is None:
        user = User(
            role=Role.CUSTOMER,
            google_sub=identity.subject,
            full_name=identity.name,
            created_at=ctx.now,
            updated_at=ctx.now,
        )
        ctx.session.add(user)
        ctx.session.flush()
    if not user.is_active:
        raise ProblemError(403, "account-disabled", "This account is disabled. Contact support.")
    user.last_login_at = ctx.now
    return user


# -- staff -------------------------------------------------------------------------


def staff_login(ctx: Ctx, email: str, password: str, totp_code: str | None, ip: str | None) -> User:
    settings = ctx.services.settings
    pepper = settings.otp_pepper.get_secret_value()
    ip_hash = hash_ip(ip, pepper)
    if ip_hash:
        retry = ctx.services.rate_limiter.hit(f"staff-login:ip:{ip_hash}", STAFF_LOGINS_PER_IP)
        if retry is not None:
            raise rate_limited(retry)
    user = ctx.session.scalar(
        select(User)
        .where(func.lower(User.email) == email.lower(), User.role.in_([Role.ADMIN, Role.VENDOR]))
        .with_for_update()
    )
    wrong = ProblemError(401, "invalid-credentials", "Wrong email or password")
    if user is None or not user.is_active or user.deleted_at is not None:
        passwords.verify_password(None, password)  # same cost as a real check
        raise wrong
    if user.locked_until and user.locked_until > ctx.now:
        raise ProblemError(
            423,
            "account-locked",
            "Too many failed attempts. Try again later.",
            extra={"locked_until": user.locked_until.isoformat()},
        )
    if not passwords.verify_password(user.password_hash, password):
        _record_failure(ctx, user)
        raise wrong
    if user.role == Role.ADMIN:
        secret = totp.decrypt(
            user.totp_secret_enc or "", settings.data_encryption_key.get_secret_value()
        )
        if secret is None:
            raise ProblemError(
                403, "totp-not-set-up", "Two-step sign-in is not set up for this account"
            )
        if not totp_code:
            raise ProblemError(401, "totp-required", "Enter the code from your authenticator app")
        if not totp.verify(secret, totp_code, ctx.now):
            _record_failure(ctx, user)
            raise ProblemError(401, "totp-invalid", "That code is not right")
    user.failed_login_count = 0
    user.locked_until = None
    user.last_login_at = ctx.now
    if user.password_hash and passwords.needs_rehash(user.password_hash):
        user.password_hash = passwords.hash_password(password)
    return user


def _record_failure(ctx: Ctx, user: User) -> None:
    settings = ctx.services.settings
    user.failed_login_count += 1
    if user.failed_login_count >= settings.staff_max_failed_logins:
        user.locked_until = ctx.now + timedelta(minutes=settings.staff_lockout_minutes)
        user.failed_login_count = 0
    ctx.session.commit()


# -- tokens ------------------------------------------------------------------------


def issue_tokens(ctx: Ctx, user: User, family_id: uuid.UUID | None = None) -> Tokens:
    settings = ctx.services.settings
    ttl = timedelta(minutes=settings.access_token_ttl_minutes)
    refresh = new_refresh_token()
    ctx.session.add(
        RefreshToken(
            user_id=user.id,
            family_id=family_id or uuid.uuid4(),
            token_hash=hash_token(refresh),
            expires_at=ctx.now + timedelta(days=settings.refresh_token_ttl_days),
            created_at=ctx.now,
        )
    )
    access = make_access_token(
        user.id, user.role.value, settings.jwt_secret.get_secret_value(), ctx.now, ttl
    )
    return Tokens(access, refresh, int(ttl.total_seconds()), user)


def refresh_tokens(ctx: Ctx, refresh: str) -> Tokens:
    token = ctx.session.scalar(
        select(RefreshToken).where(RefreshToken.token_hash == hash_token(refresh)).with_for_update()
    )
    invalid_token = ProblemError(401, "invalid-refresh-token", "Please sign in again")
    if token is None:
        raise invalid_token
    if token.used_at is not None or token.revoked_at is not None:
        # A refresh token was used twice: someone may have stolen it. End the whole session.
        revoke_family(ctx, token.family_id)
        ctx.session.commit()
        log.warning("refresh token reuse detected", extra={"user_id": str(token.user_id)})
        raise ProblemError(401, "refresh-token-reused", "Please sign in again")
    if token.expires_at <= ctx.now:
        raise invalid_token
    user = ctx.session.get(User, token.user_id)
    if user is None or not user.is_active or user.deleted_at is not None:
        raise invalid_token
    token.used_at = ctx.now
    return issue_tokens(ctx, user, family_id=token.family_id)


def revoke_family(ctx: Ctx, family_id: uuid.UUID) -> None:
    ctx.session.execute(
        update(RefreshToken)
        .where(RefreshToken.family_id == family_id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=ctx.now)
    )


def logout(ctx: Ctx, refresh: str) -> None:
    token = ctx.session.scalar(
        select(RefreshToken).where(RefreshToken.token_hash == hash_token(refresh))
    )
    if token is not None:
        revoke_family(ctx, token.family_id)


def revoke_all(ctx: Ctx, user: User) -> None:
    ctx.session.execute(
        update(RefreshToken)
        .where(RefreshToken.user_id == user.id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=ctx.now)
    )


# -- staff accounts ---------------------------------------------------------------


@dataclass(frozen=True)
class NewStaff:
    user: User
    temporary_password: str
    totp_uri: str | None
    totp_secret: str | None


def create_staff(
    ctx: Ctx,
    *,
    email: str,
    full_name: str,
    role: Role,
    vendor_id: uuid.UUID | None = None,
    password: str | None = None,
    totp_secret: str | None = None,
) -> NewStaff:
    if role not in (Role.ADMIN, Role.VENDOR):
        raise ValueError("staff role required")
    existing = ctx.session.scalar(select(User.id).where(func.lower(User.email) == email.lower()))
    if existing is not None:
        raise conflict("email-in-use", "This email already has an account")
    temporary = password or passwords.temporary_password()
    secret = totp_secret or totp.new_secret() if role == Role.ADMIN else None
    key = ctx.services.settings.data_encryption_key.get_secret_value()
    user = User(
        role=role,
        email=email.lower(),
        full_name=full_name,
        vendor_id=vendor_id,
        password_hash=passwords.hash_password(temporary),
        totp_secret_enc=totp.encrypt(secret, key) if secret else None,
        terms_accepted_at=ctx.now,
        created_at=ctx.now,
        updated_at=ctx.now,
    )
    ctx.session.add(user)
    ctx.session.flush()
    return NewStaff(
        user, temporary, totp.provisioning_uri(secret, email) if secret else None, secret
    )


def reset_staff_login(ctx: Ctx, email: str) -> NewStaff:
    """A new temporary password, and for an admin a new authenticator secret, for
    a staff member who lost theirs (docs/RUNBOOK.md). Clears any lockout and
    signs out every session. A disabled account stays disabled."""
    user = ctx.session.scalar(
        select(User)
        .where(func.lower(User.email) == email.lower(), User.role.in_((Role.ADMIN, Role.VENDOR)))
        .with_for_update()
    )
    if user is None:
        raise not_found("Staff member")
    temporary = passwords.temporary_password()
    user.password_hash = passwords.hash_password(temporary)
    secret = totp.new_secret() if user.role == Role.ADMIN else None
    if secret:
        key = ctx.services.settings.data_encryption_key.get_secret_value()
        user.totp_secret_enc = totp.encrypt(secret, key)
    user.failed_login_count = 0
    user.locked_until = None
    user.updated_at = ctx.now
    revoke_all(ctx, user)
    return NewStaff(
        user,
        temporary,
        totp.provisioning_uri(secret, user.email or email) if secret else None,
        secret,
    )


def reencrypt_totp_secrets(ctx: Ctx, old_key: str) -> tuple[int, int]:
    """Re-encrypt every authenticator secret from old_key to the current
    DATA_ENCRYPTION_KEY. Returns (re-encrypted, already on the current key).
    Safe to run twice. Refuses, changing nothing, if a secret opens with
    neither key."""
    new_key = ctx.services.settings.data_encryption_key.get_secret_value()
    users = ctx.session.scalars(
        select(User).where(User.totp_secret_enc.is_not(None)).with_for_update()
    ).all()
    rotated = current = 0
    for user in users:
        sealed = user.totp_secret_enc or ""
        secret = totp.decrypt(sealed, old_key)
        if secret is None:
            if totp.decrypt(sealed, new_key) is None:
                ctx.session.rollback()
                raise ValueError(f"The authenticator secret of {user.email} opens with neither key")
            current += 1
            continue
        user.totp_secret_enc = totp.encrypt(secret, new_key)
        user.updated_at = ctx.now
        rotated += 1
    return rotated, current
