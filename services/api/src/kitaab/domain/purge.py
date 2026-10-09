"""Storage auto-purge (brief section 3.11). Runs hourly.

Deletes, after PURGE_DAYS (default 7):
  - PDFs of delivered orders (counted from delivery),
  - PDFs of cancelled, rejected and failed-delivery orders (from the terminal state; D-016),
and after 24 hours, uploads never attached to an order. For deleted accounts it
also removes the shipping details of orders that have finished (D-019).

Each file: all object versions deleted, stray multipart upload aborted,
object_key set to null and purged_at set. Page count, hash and money stay.
"""

import logging
from dataclasses import asdict, dataclass, field
from datetime import timedelta

from sqlalchemy import exists, select

from kitaab.domain import audit
from kitaab.domain.context import Ctx
from kitaab.domain.enums import TERMINAL_STATUSES, OrderStatus, UploadStatus
from kitaab.models import Order, Upload, User

log = logging.getLogger(__name__)

PURGED_AFTER_EXIT = (OrderStatus.CANCELLED, OrderStatus.REJECTED, OrderStatus.DELIVERY_FAILED)
DONE_STATUSES = TERMINAL_STATUSES | {OrderStatus.DELIVERED}


@dataclass
class PurgeReport:
    dry_run: bool
    delivered_files: int = 0
    exited_files: int = 0
    unattached_uploads: int = 0
    object_versions_deleted: int = 0
    multipart_aborted: int = 0
    shipping_scrubbed: int = 0
    errors: int = 0
    upload_ids: list[str] = field(default_factory=list)


def _purge_upload(ctx: Ctx, upload: Upload, report: PurgeReport) -> bool:
    report.upload_ids.append(str(upload.id))
    if report.dry_run:
        return True
    store = ctx.services.store
    try:
        if upload.object_key and upload.s3_upload_id:
            store.abort_multipart_upload(upload.object_key, upload.s3_upload_id)
            report.multipart_aborted += 1
        if upload.object_key:
            report.object_versions_deleted += store.delete_all_versions(upload.object_key)
    except Exception:
        log.exception("purge failed for upload", extra={"upload_id": str(upload.id)})
        report.errors += 1
        return False
    upload.object_key = None
    upload.s3_upload_id = None
    upload.status = UploadStatus.PURGED
    upload.purged_at = ctx.now
    return True


def run_purge(ctx: Ctx, *, dry_run: bool | None = None) -> PurgeReport:
    settings = ctx.services.settings
    report = PurgeReport(dry_run=settings.purge_dry_run if dry_run is None else dry_run)
    keep_for = timedelta(days=settings.purge_days)
    cutoff = ctx.now - keep_for

    delivered = ctx.session.scalars(
        select(Upload)
        .join(Order, Order.upload_id == Upload.id)
        .where(
            Upload.object_key.is_not(None),
            Order.delivered_at.is_not(None),
            Order.delivered_at <= cutoff,
        )
        .with_for_update(of=Upload)
    ).all()
    for upload in delivered:
        if _purge_upload(ctx, upload, report):
            report.delivered_files += 1

    exited = ctx.session.scalars(
        select(Upload)
        .join(Order, Order.upload_id == Upload.id)
        .where(
            Upload.object_key.is_not(None),
            Order.status.in_(PURGED_AFTER_EXIT),
            Order.terminal_at.is_not(None),
            Order.terminal_at <= cutoff,
        )
        .with_for_update(of=Upload)
    ).all()
    for upload in exited:
        if _purge_upload(ctx, upload, report):
            report.exited_files += 1

    unattached_cutoff = ctx.now - timedelta(hours=settings.unattached_upload_ttl_hours)
    unattached = ctx.session.scalars(
        select(Upload)
        .where(
            Upload.status != UploadStatus.PURGED,
            Upload.created_at <= unattached_cutoff,
            ~exists().where(Order.upload_id == Upload.id),
            (Upload.object_key.is_not(None)) | (Upload.s3_upload_id.is_not(None)),
        )
        .with_for_update()
    ).all()
    for upload in unattached:
        if _purge_upload(ctx, upload, report):
            report.unattached_uploads += 1

    scrub = ctx.session.scalars(
        select(Order)
        .join(User, User.id == Order.user_id)
        .where(
            User.deleted_at.is_not(None),
            Order.pii_scrubbed_at.is_(None),
            Order.status.in_(DONE_STATUSES),
        )
        .with_for_update(of=Order)
    ).all()
    for order in scrub:
        report.shipping_scrubbed += 1
        if not report.dry_run:
            scrub_shipping(ctx, order)
            if order.upload is not None and order.upload.object_key:
                _purge_upload(ctx, order.upload, report)

    details = asdict(report)
    details.pop("upload_ids")
    audit.record(ctx, "purge.run", "storage", None, **details)
    log.info("purge finished", extra=details)
    return report


def scrub_shipping(ctx: Ctx, order: Order) -> None:
    order.ship_recipient_name = None
    order.ship_recipient_phone_e164 = None
    order.ship_area = None
    order.ship_street_address = None
    order.ship_landmark = None
    order.book_notes = None
    order.pii_scrubbed_at = ctx.now
