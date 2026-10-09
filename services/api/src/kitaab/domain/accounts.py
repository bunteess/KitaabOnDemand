"""In-app account deletion (brief section 3.4, D-019).

Removes personal data and files at once and keeps anonymised financial
records. Orders that can still be cancelled are cancelled. Orders already being
printed or shipped keep only what delivery needs; the hourly purge removes
those details once the order finishes.
"""

from dataclasses import dataclass

from sqlalchemy import delete, select

from kitaab.domain import auth, purge
from kitaab.domain.context import Ctx
from kitaab.domain.enums import TERMINAL_STATUSES, Actor, OrderStatus, UploadStatus
from kitaab.domain.orders import service as orders
from kitaab.models import Address, Device, Notification, Order, OtpChallenge, Upload, User


@dataclass(frozen=True)
class DeletionResult:
    cancelled: list[str]
    retained: list[str]


def delete_account(ctx: Ctx, user: User) -> DeletionResult:
    cancelled: list[str] = []
    retained: list[str] = []
    order_ids = ctx.session.scalars(select(Order.id).where(Order.user_id == user.id)).all()
    for order_id in order_ids:
        order = orders.lock(ctx, order_id)
        if order.status in TERMINAL_STATUSES or order.status == OrderStatus.DELIVERED:
            purge.scrub_shipping(ctx, order)
            continue
        if orders.can(order, Actor.USER, OrderStatus.CANCELLED):
            orders.transition(
                ctx, order, OrderStatus.CANCELLED, actor=Actor.USER, reason="Account deleted"
            )
            purge.scrub_shipping(ctx, order)
            cancelled.append(order.code)
        else:
            retained.append(order.code)

    # Files not needed by an in-flight order go now.
    in_flight_uploads = set(
        ctx.session.scalars(
            select(Order.upload_id).where(
                Order.user_id == user.id, Order.code.in_(retained), Order.upload_id.is_not(None)
            )
        )
    )
    for upload in ctx.session.scalars(select(Upload).where(Upload.user_id == user.id)):
        if upload.id in in_flight_uploads:
            continue
        store = ctx.services.store
        if upload.object_key and upload.s3_upload_id:
            store.abort_multipart_upload(upload.object_key, upload.s3_upload_id)
        if upload.object_key:
            store.delete_all_versions(upload.object_key)
        upload.object_key = None
        upload.s3_upload_id = None
        upload.filename = None
        upload.status = UploadStatus.PURGED
        upload.purged_at = ctx.now

    ctx.session.execute(delete(Address).where(Address.user_id == user.id))
    ctx.session.execute(delete(Device).where(Device.user_id == user.id))
    ctx.session.execute(delete(Notification).where(Notification.user_id == user.id))
    if user.phone_e164:
        ctx.session.execute(delete(OtpChallenge).where(OtpChallenge.phone_e164 == user.phone_e164))
    auth.revoke_all(ctx, user)

    # The row stays (orders and the ledger point at it) but holds nothing personal.
    user.full_name = None
    user.phone_e164 = None
    user.phone_verified_at = None
    user.email = None
    user.google_sub = None
    user.is_active = False
    user.deleted_at = ctx.now
    return DeletionResult(cancelled, retained)
