import uuid
from contextlib import suppress

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import ColumnElement, func, or_, select

from kitaab.api.v1.presenters import admin_order_summary, staff_out, vendor_out
from kitaab.domain import audit
from kitaab.domain import auth as auth_domain
from kitaab.domain.context import Ctx
from kitaab.domain.enums import Role
from kitaab.models import City, Order, User, Vendor
from kitaab.phone import InvalidPhoneError, mask_phone, normalize_pk_mobile
from kitaab.problems import conflict, invalid, not_found
from kitaab.schemas.admin import (
    CustomerDetail,
    CustomerPage,
    CustomerSummary,
    StaffUserCreate,
    StaffUserCreated,
    StaffUserOut,
    StaffUserUpdate,
    VendorIn,
    VendorOut,
)
from kitaab.security.deps import admin_ctx, me

router = APIRouter(prefix="/admin", tags=["admin: people"])


def _apply_vendor(ctx: Ctx, vendor: Vendor, body: VendorIn) -> None:
    try:
        phone = normalize_pk_mobile(body.contact_phone)
    except InvalidPhoneError as error:
        raise invalid("invalid-phone", "Enter a Pakistani mobile number for the contact") from error
    if body.city_id is not None and ctx.session.get(City, body.city_id) is None:
        raise invalid("unknown-city", "Choose a city from the list")
    vendor.name = body.name
    vendor.contact_name = body.contact_name
    vendor.contact_phone_e164 = phone
    vendor.email = body.email
    vendor.city_id = body.city_id
    vendor.address = body.address
    vendor.is_active = body.is_active


@router.get("/vendors")
def admin_list_vendors(
    include_inactive: bool = False, ctx: Ctx = Depends(admin_ctx)
) -> list[VendorOut]:
    query = select(Vendor).order_by(Vendor.name)
    if not include_inactive:
        query = query.where(Vendor.is_active)
    return [vendor_out(v) for v in ctx.session.scalars(query)]


@router.post("/vendors", status_code=status.HTTP_201_CREATED)
def admin_create_vendor(body: VendorIn, ctx: Ctx = Depends(admin_ctx)) -> VendorOut:
    vendor = Vendor(created_at=ctx.now, updated_at=ctx.now)
    _apply_vendor(ctx, vendor, body)
    ctx.session.add(vendor)
    ctx.session.flush()
    audit.record(ctx, "vendor.create", "vendor", vendor.id)
    ctx.session.commit()
    return vendor_out(vendor)


@router.put("/vendors/{vendor_id}")
def admin_update_vendor(
    vendor_id: uuid.UUID, body: VendorIn, ctx: Ctx = Depends(admin_ctx)
) -> VendorOut:
    vendor = ctx.session.get(Vendor, vendor_id)
    if vendor is None:
        raise not_found("Vendor")
    _apply_vendor(ctx, vendor, body)
    audit.record(ctx, "vendor.update", "vendor", vendor.id, is_active=vendor.is_active)
    ctx.session.commit()
    return vendor_out(vendor)


@router.get("/vendors/{vendor_id}/users")
def admin_list_vendor_users(
    vendor_id: uuid.UUID, ctx: Ctx = Depends(admin_ctx)
) -> list[StaffUserOut]:
    rows = ctx.session.scalars(
        select(User)
        .where(User.vendor_id == vendor_id, User.role == Role.VENDOR)
        .order_by(User.email)
    )
    return [staff_out(ctx, u) for u in rows]


def _created(ctx: Ctx, new: auth_domain.NewStaff) -> StaffUserCreated:
    return StaffUserCreated(
        user=staff_out(ctx, new.user),
        temporary_password=new.temporary_password,
        totp_provisioning_uri=new.totp_uri,
    )


@router.post("/vendors/{vendor_id}/users", status_code=status.HTTP_201_CREATED)
def admin_create_vendor_user(
    vendor_id: uuid.UUID, body: StaffUserCreate, ctx: Ctx = Depends(admin_ctx)
) -> StaffUserCreated:
    if ctx.session.get(Vendor, vendor_id) is None:
        raise not_found("Vendor")
    new = auth_domain.create_staff(
        ctx, email=body.email, full_name=body.full_name, role=Role.VENDOR, vendor_id=vendor_id
    )
    audit.record(ctx, "staff.create", "user", new.user.id, role="VENDOR", vendor_id=str(vendor_id))
    ctx.session.commit()
    return _created(ctx, new)


@router.get("/staff")
def admin_list_admins(ctx: Ctx = Depends(admin_ctx)) -> list[StaffUserOut]:
    rows = ctx.session.scalars(select(User).where(User.role == Role.ADMIN).order_by(User.email))
    return [staff_out(ctx, u) for u in rows]


@router.post("/staff", status_code=status.HTTP_201_CREATED)
def admin_create_admin(body: StaffUserCreate, ctx: Ctx = Depends(admin_ctx)) -> StaffUserCreated:
    """Create another admin. The response includes a TOTP setup link, shown once."""
    new = auth_domain.create_staff(ctx, email=body.email, full_name=body.full_name, role=Role.ADMIN)
    audit.record(ctx, "staff.create", "user", new.user.id, role="ADMIN")
    ctx.session.commit()
    return _created(ctx, new)


@router.patch("/staff/{user_id}")
def admin_update_staff_user(
    user_id: uuid.UUID, body: StaffUserUpdate, ctx: Ctx = Depends(admin_ctx)
) -> StaffUserOut:
    """Deactivate, reactivate or unlock an admin or vendor user."""
    user = ctx.session.get(User, user_id)
    if user is None or user.role not in (Role.ADMIN, Role.VENDOR):
        raise not_found("User")
    if body.is_active is False and user.id == me(ctx).id:
        raise conflict("cannot-deactivate-self", "You cannot deactivate your own account")
    if body.is_active is not None:
        user.is_active = body.is_active
        if not body.is_active:
            auth_domain.revoke_all(ctx, user)
    if body.unlock:
        user.locked_until = None
        user.failed_login_count = 0
    audit.record(
        ctx, "staff.update", "user", user.id, is_active=user.is_active, unlocked=body.unlock
    )
    ctx.session.commit()
    return staff_out(ctx, user)


@router.get("/customers")
def admin_list_customers(
    q: str | None = Query(None, max_length=100),
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    ctx: Ctx = Depends(admin_ctx),
) -> CustomerPage:
    """Read-only support view."""
    query = select(User).where(User.role == Role.CUSTOMER)
    if q and q.strip():
        conditions: list[ColumnElement[bool]] = [User.full_name.ilike(f"%{q.strip()}%")]
        with suppress(InvalidPhoneError):
            conditions.append(User.phone_e164 == normalize_pk_mobile(q))
        query = query.where(or_(*conditions))
    total = ctx.session.scalar(select(func.count()).select_from(query.subquery())) or 0
    users = ctx.session.scalars(
        query.order_by(User.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    ).all()
    counts = (
        dict(
            ctx.session.execute(
                select(Order.user_id, func.count())
                .where(Order.user_id.in_([u.id for u in users]))
                .group_by(Order.user_id)
            ).all()
        )
        if users
        else {}
    )
    return CustomerPage(
        items=[
            CustomerSummary(
                id=u.id,
                full_name=u.full_name,
                phone_masked=mask_phone(u.phone_e164),
                order_count=counts.get(u.id, 0),
                is_review_account=u.is_review_account,
                deleted=u.deleted_at is not None,
                created_at=u.created_at,
            )
            for u in users
        ],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/customers/{user_id}")
def admin_get_customer(user_id: uuid.UUID, ctx: Ctx = Depends(admin_ctx)) -> CustomerDetail:
    user = ctx.session.get(User, user_id)
    if user is None or user.role != Role.CUSTOMER:
        raise not_found("Customer")
    rows = ctx.session.scalars(
        select(Order).where(Order.user_id == user.id).order_by(Order.created_at.desc()).limit(100)
    )
    audit.record(ctx, "customer.view", "user", user.id)
    ctx.session.commit()
    return CustomerDetail(
        id=user.id,
        full_name=user.full_name,
        phone_e164=user.phone_e164,
        email=user.email,
        google_linked=user.google_sub is not None,
        is_review_account=user.is_review_account,
        created_at=user.created_at,
        deleted_at=user.deleted_at,
        orders=[admin_order_summary(o) for o in rows],
    )
