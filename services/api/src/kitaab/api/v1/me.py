import uuid

from fastapi import Depends, Request, status
from sqlalchemy import delete, select, update

from kitaab.api.routing import api_router
from kitaab.api.v1.presenters import address_out, me_out
from kitaab.domain import accounts
from kitaab.domain import auth as auth_domain
from kitaab.domain.context import Ctx
from kitaab.models import Address, City, Device
from kitaab.phone import InvalidPhoneError, normalize_pk_mobile
from kitaab.problems import conflict, invalid, not_found
from kitaab.schemas.auth import OtpRequest, OtpRequested, OtpVerify
from kitaab.schemas.catalog import AddressIn, AddressOut
from kitaab.schemas.me import (
    AccountDeletion,
    AccountDeletionResult,
    DeviceRegister,
    DeviceUnregister,
    MeOut,
    MeUpdate,
    TermsAccept,
)
from kitaab.security.deps import client_ip, customer_ctx, me, user_ctx

router = api_router(prefix="/me", tags=["me"])

MAX_ADDRESSES = 20


@router.get("")
def get_me(ctx: Ctx = Depends(user_ctx)) -> MeOut:
    return me_out(ctx, me(ctx))


@router.patch("")
def update_me(body: MeUpdate, ctx: Ctx = Depends(user_ctx)) -> MeOut:
    user = me(ctx)
    user.full_name = body.full_name
    ctx.session.commit()
    return me_out(ctx, user)


@router.post("/phone/request", status_code=status.HTTP_202_ACCEPTED)
def request_phone_link(
    body: OtpRequest, request: Request, ctx: Ctx = Depends(customer_ctx)
) -> OtpRequested:
    """Send a code to add a phone number to a Google account."""
    sent = auth_domain.request_otp(
        ctx, body.phone, client_ip(request), purpose=auth_domain.PURPOSE_LINK, user=me(ctx)
    )
    ctx.session.commit()
    return OtpRequested(
        phone_e164=sent.phone_e164,
        expires_in_seconds=sent.expires_in_seconds,
        resend_after_seconds=sent.resend_after_seconds,
    )


@router.post("/phone/verify")
def verify_phone_link(body: OtpVerify, request: Request, ctx: Ctx = Depends(customer_ctx)) -> MeOut:
    phone = auth_domain.verify_otp(
        ctx, body.phone, body.code, client_ip(request), purpose=auth_domain.PURPOSE_LINK
    )
    auth_domain.link_phone(ctx, me(ctx), phone)
    ctx.session.commit()
    return me_out(ctx, me(ctx))


@router.post("/terms")
def accept_terms(body: TermsAccept, ctx: Ctx = Depends(user_ctx)) -> MeOut:
    """Record acceptance of the current terms and privacy policy."""
    if body.terms_version != ctx.services.settings.terms_version:
        raise conflict(
            "terms-outdated",
            "Please read the latest terms",
            current=ctx.services.settings.terms_version,
        )
    user = me(ctx)
    user.terms_version = body.terms_version
    user.terms_accepted_at = ctx.now
    ctx.session.commit()
    return me_out(ctx, user)


@router.post("/delete")
def delete_account(
    body: AccountDeletion, ctx: Ctx = Depends(customer_ctx)
) -> AccountDeletionResult:
    """Delete the account and personal data now. Financial records are kept anonymised."""
    result = accounts.delete_account(ctx, me(ctx))
    ctx.session.commit()
    return AccountDeletionResult(
        cancelled_order_codes=result.cancelled, retained_order_codes=result.retained
    )


@router.post("/devices", status_code=status.HTTP_204_NO_CONTENT)
def register_device(body: DeviceRegister, ctx: Ctx = Depends(customer_ctx)) -> None:
    device = ctx.session.scalar(select(Device).where(Device.push_token == body.push_token))
    if device is None:
        ctx.session.add(
            Device(
                user_id=me(ctx).id,
                platform=body.platform,
                push_token=body.push_token,
                created_at=ctx.now,
                last_seen_at=ctx.now,
            )
        )
    else:
        # A token moves with the phone: the latest account to sign in owns it.
        device.user_id = me(ctx).id
        device.last_seen_at = ctx.now
    ctx.session.commit()


@router.post("/devices/unregister", status_code=status.HTTP_204_NO_CONTENT)
def unregister_device(body: DeviceUnregister, ctx: Ctx = Depends(customer_ctx)) -> None:
    ctx.session.execute(
        delete(Device).where(Device.push_token == body.push_token, Device.user_id == me(ctx).id)
    )
    ctx.session.commit()


def _owned(ctx: Ctx, address_id: uuid.UUID) -> Address:
    address = ctx.session.get(Address, address_id)
    if address is None or address.user_id != me(ctx).id:
        raise not_found("Address")
    return address


def _apply(ctx: Ctx, address: Address, body: AddressIn) -> None:
    try:
        phone = normalize_pk_mobile(body.recipient_phone)
    except InvalidPhoneError as error:
        raise invalid(
            "invalid-phone", "Enter a Pakistani mobile number for the recipient"
        ) from error
    city = ctx.session.get(City, body.city_id)
    if city is None or not city.is_active:
        raise invalid("city-not-served", "We do not deliver to this city yet")
    address.label = body.label
    address.recipient_name = body.recipient_name
    address.recipient_phone_e164 = phone
    address.city_id = city.id
    address.area = body.area
    address.street_address = body.street_address
    address.landmark = body.landmark
    address.updated_at = ctx.now
    has_default = ctx.session.scalar(
        select(Address.id).where(
            Address.user_id == me(ctx).id, Address.is_default, Address.id != address.id
        )
    )
    address.is_default = body.is_default or has_default is None
    if address.is_default:
        ctx.session.execute(
            update(Address)
            .where(Address.user_id == me(ctx).id, Address.id != address.id)
            .values(is_default=False)
        )


@router.get("/addresses")
def list_addresses(ctx: Ctx = Depends(customer_ctx)) -> list[AddressOut]:
    rows = ctx.session.scalars(
        select(Address)
        .where(Address.user_id == me(ctx).id)
        .order_by(Address.is_default.desc(), Address.created_at)
    )
    return [address_out(a) for a in rows]


@router.post("/addresses", status_code=status.HTTP_201_CREATED)
def create_address(body: AddressIn, ctx: Ctx = Depends(customer_ctx)) -> AddressOut:
    count = len(ctx.session.scalars(select(Address.id).where(Address.user_id == me(ctx).id)).all())
    if count >= MAX_ADDRESSES:
        raise conflict("too-many-addresses", f"You can save up to {MAX_ADDRESSES} addresses")
    address = Address(id=uuid.uuid4(), user_id=me(ctx).id, created_at=ctx.now, updated_at=ctx.now)
    _apply(ctx, address, body)
    ctx.session.add(address)
    ctx.session.commit()
    ctx.session.refresh(address)
    return address_out(address)


@router.put("/addresses/{address_id}")
def update_address(
    address_id: uuid.UUID, body: AddressIn, ctx: Ctx = Depends(customer_ctx)
) -> AddressOut:
    address = _owned(ctx, address_id)
    _apply(ctx, address, body)
    ctx.session.commit()
    ctx.session.refresh(address)
    return address_out(address)


@router.delete("/addresses/{address_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_address(address_id: uuid.UUID, ctx: Ctx = Depends(customer_ctx)) -> None:
    address = _owned(ctx, address_id)
    was_default = address.is_default
    ctx.session.delete(address)
    ctx.session.flush()
    if was_default:
        replacement = ctx.session.scalar(
            select(Address)
            .where(Address.user_id == me(ctx).id)
            .order_by(Address.created_at)
            .limit(1)
        )
        if replacement is not None:
            replacement.is_default = True
    ctx.session.commit()
