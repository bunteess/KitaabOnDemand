"""Resumable PDF uploads straight to object storage (brief section 3.3).

Size is enforced four times: the declared size at creation, the number of part
URLs handed out, the summed part sizes before completion, and the object the
worker reads.
"""

import logging
import math
import tempfile
import uuid
from datetime import datetime, timedelta
from pathlib import Path

from kitaab.container import Services
from kitaab.domain import notification_texts as texts
from kitaab.domain import notifications
from kitaab.domain.context import Ctx
from kitaab.domain.enums import NotificationKind, UploadRejection, UploadStatus
from kitaab.models import Upload, User
from kitaab.pdf.validate import validate_pdf
from kitaab.problems import ProblemError, conflict, invalid, not_found
from kitaab.providers.storage import UploadedPart
from kitaab.schemas.uploads import UploadCreate
from kitaab.security.ratelimit import Limit
from kitaab.tx import after_commit

log = logging.getLogger(__name__)

UPLOADS_PER_HOUR = Limit(20, 3600)


def _safe_filename(name: str) -> str:
    base = Path(name.replace("\\", "/")).name.strip()
    cleaned = "".join(c for c in base if c.isprintable() and c not in '<>:"|?*')[:200]
    return cleaned or "document.pdf"


def create(ctx: Ctx, user: User, body: UploadCreate) -> tuple[Upload, list[tuple[int, str]]]:
    settings = ctx.services.settings
    if not body.copyright_declared:
        raise invalid("copyright-required", "Please confirm you have the right to print this file")
    if body.size_bytes > settings.max_upload_bytes:
        raise invalid(
            "upload-too-large",
            "The file is larger than 150 MB",
            max_bytes=settings.max_upload_bytes,
        )
    retry_after = ctx.services.rate_limiter.hit(f"uploads:{user.id}", UPLOADS_PER_HOUR)
    if retry_after is not None:
        raise ProblemError(
            429,
            "rate-limited",
            "Too many uploads. Please wait and try again.",
            headers={"Retry-After": str(retry_after)},
        )
    part_count = math.ceil(body.size_bytes / settings.upload_part_bytes)
    key = f"uploads/{uuid.uuid4()}.pdf"
    s3_upload_id = ctx.services.store.create_multipart_upload(key, "application/pdf")
    upload = Upload(
        user_id=user.id,
        status=UploadStatus.AWAITING_PARTS,
        object_key=key,
        s3_upload_id=s3_upload_id,
        filename=_safe_filename(body.filename),
        declared_size_bytes=body.size_bytes,
        part_count=part_count,
        client_page_count=body.client_page_count,
        copyright_declared_at=ctx.now,
        created_at=ctx.now,
    )
    ctx.session.add(upload)
    ctx.session.flush()
    return upload, part_urls(ctx, upload, list(range(1, part_count + 1)))


def get_owned(ctx: Ctx, user: User, upload_id: uuid.UUID, *, lock: bool = False) -> Upload:
    upload = ctx.session.get(Upload, upload_id, with_for_update=lock)
    if upload is None or upload.user_id != user.id:
        raise not_found("Upload")
    return upload


def uploaded_parts(ctx: Ctx, upload: Upload) -> list[UploadedPart]:
    if (
        upload.status != UploadStatus.AWAITING_PARTS
        or not upload.object_key
        or not upload.s3_upload_id
    ):
        return []
    return ctx.services.store.list_parts(upload.object_key, upload.s3_upload_id)


def part_urls(ctx: Ctx, upload: Upload, numbers: list[int]) -> list[tuple[int, str]]:
    if (
        upload.status != UploadStatus.AWAITING_PARTS
        or not upload.object_key
        or not upload.s3_upload_id
    ):
        raise conflict("upload-closed", "This upload is no longer accepting parts")
    bad = [n for n in numbers if not 1 <= n <= upload.part_count]
    if bad:
        raise invalid("invalid-part", f"Part numbers must be between 1 and {upload.part_count}")
    ttl = ctx.services.settings.upload_url_ttl_seconds
    store = ctx.services.store
    return [
        (n, store.presign_upload_part(upload.object_key, upload.s3_upload_id, n, ttl))
        for n in sorted(set(numbers))
    ]


def urls_expire_at(ctx: Ctx) -> datetime:
    return ctx.now + timedelta(seconds=ctx.services.settings.upload_url_ttl_seconds)


def complete(ctx: Ctx, upload: Upload) -> Upload:
    if upload.status == UploadStatus.VALIDATING:
        return upload  # a retried "complete" after a dropped response
    if (
        upload.status != UploadStatus.AWAITING_PARTS
        or not upload.object_key
        or not upload.s3_upload_id
    ):
        raise conflict("upload-closed", "This upload is already finished")
    store = ctx.services.store
    parts = store.list_parts(upload.object_key, upload.s3_upload_id)
    numbers = {p.number for p in parts}
    missing = [n for n in range(1, upload.part_count + 1) if n not in numbers]
    if missing:
        raise conflict(
            "upload-incomplete", "Some parts have not arrived yet", missing_parts=missing[:50]
        )
    total = sum(p.size for p in parts if p.number <= upload.part_count)
    limit = min(upload.declared_size_bytes, ctx.services.settings.max_upload_bytes)
    if total > limit or any(p.number > upload.part_count for p in parts):
        store.abort_multipart_upload(upload.object_key, upload.s3_upload_id)
        upload.status = UploadStatus.REJECTED
        upload.rejection_code = (
            UploadRejection.TOO_LARGE
            if total > ctx.services.settings.max_upload_bytes
            else UploadRejection.SIZE_MISMATCH
        )
        upload.s3_upload_id = None
        upload.object_key = None
        return upload
    store.complete_multipart_upload(upload.object_key, upload.s3_upload_id, parts)
    upload.status = UploadStatus.VALIDATING
    upload.size_bytes = total
    upload.completed_at = ctx.now
    upload.s3_upload_id = None
    upload_id = str(upload.id)
    tasks = ctx.services.tasks
    after_commit(ctx.session, lambda: tasks.enqueue("validate_upload", upload_id=upload_id))
    return upload


def abort(ctx: Ctx, upload: Upload) -> None:
    if upload.status == UploadStatus.AWAITING_PARTS and upload.object_key and upload.s3_upload_id:
        ctx.services.store.abort_multipart_upload(upload.object_key, upload.s3_upload_id)
        upload.s3_upload_id = None
        upload.status = UploadStatus.ABORTED
    elif upload.status in (UploadStatus.VALID, UploadStatus.REJECTED, UploadStatus.VALIDATING):
        raise conflict("upload-closed", "This upload is already finished")


def run_validation(services: Services, upload_id: str) -> UploadStatus | None:
    """Background job: download the object and run the PDF checks."""
    with services.session() as session:
        ctx = Ctx(session, services)
        upload = session.get(Upload, uuid.UUID(upload_id), with_for_update=True)
        if upload is None or upload.status != UploadStatus.VALIDATING or not upload.object_key:
            return None
        key = upload.object_key
        settings = services.settings
        with tempfile.TemporaryDirectory(prefix="kitaab-") as tmp:
            path = Path(tmp) / "upload.pdf"
            stored = services.store.object_size(key)
            if stored is None:
                result_rejection: UploadRejection | None = UploadRejection.CORRUPT
                check = None
            elif stored > settings.max_upload_bytes:
                result_rejection = UploadRejection.TOO_LARGE
                check = None
            else:
                services.store.download_to_file(key, path)
                check = validate_pdf(
                    path,
                    max_bytes=settings.max_upload_bytes,
                    scanner=services.scanner,
                    require_scan=settings.is_production,
                )
                result_rejection = check.rejection
        upload.validated_at = ctx.now
        if check is not None:
            upload.sha256 = check.sha256
            upload.size_bytes = check.size_bytes
        if result_rejection is None and check is not None:
            upload.status = UploadStatus.VALID
            upload.page_count = check.page_count
            title, body = texts.upload_valid(check.page_count or 0)
        else:
            log.info(
                "upload rejected",
                extra={
                    "upload_id": upload_id,
                    "code": str(result_rejection),
                    "detail": check.detail if check else None,
                },
            )
            upload.status = UploadStatus.REJECTED
            upload.rejection_code = result_rejection
            upload.page_count = check.page_count if check else None
            # Rejected files are deleted at once: they will never be printed.
            services.store.delete_all_versions(key)
            upload.object_key = None
            upload.purged_at = ctx.now
            title, body = texts.upload_rejected()
        if upload.user_id is not None:
            notifications.notify(ctx, upload.user_id, NotificationKind.UPLOAD_RESULT, title, body)
        session.commit()
        return upload.status
