import uuid

from fastapi import APIRouter, Depends, status

from kitaab.api.v1.presenters import upload_out
from kitaab.domain import uploads as upload_domain
from kitaab.domain.context import Ctx
from kitaab.schemas.uploads import (
    PartUrl,
    PartUrls,
    PartUrlsRequest,
    UploadCreate,
    UploadOut,
    UploadSession,
)
from kitaab.security.deps import customer_ctx, me

router = APIRouter(prefix="/uploads", tags=["uploads"])


@router.post("", status_code=status.HTTP_201_CREATED)
def create_upload(body: UploadCreate, ctx: Ctx = Depends(customer_ctx)) -> UploadSession:
    """Start a resumable upload. Returns presigned URLs for every 8 MB part."""
    upload, urls = upload_domain.create(ctx, me(ctx), body)
    ctx.session.commit()
    return UploadSession(
        upload=upload_out(upload),
        part_size_bytes=ctx.services.settings.upload_part_bytes,
        part_count=upload.part_count,
        parts=[PartUrl(number=n, url=u) for n, u in urls],
        urls_expire_at=upload_domain.urls_expire_at(ctx),
    )


@router.get("/{upload_id}")
def get_upload(upload_id: uuid.UUID, ctx: Ctx = Depends(customer_ctx)) -> UploadOut:
    """Status, validation result and, while uploading, the parts storage already has."""
    upload = upload_domain.get_owned(ctx, me(ctx), upload_id)
    return upload_out(upload, [p.number for p in upload_domain.uploaded_parts(ctx, upload)])


@router.post("/{upload_id}/parts")
def get_part_urls(
    upload_id: uuid.UUID, body: PartUrlsRequest, ctx: Ctx = Depends(customer_ctx)
) -> PartUrls:
    """Fresh presigned URLs for the given parts, used when resuming."""
    upload = upload_domain.get_owned(ctx, me(ctx), upload_id)
    urls = upload_domain.part_urls(ctx, upload, body.part_numbers)
    return PartUrls(
        parts=[PartUrl(number=n, url=u) for n, u in urls],
        urls_expire_at=upload_domain.urls_expire_at(ctx),
    )


@router.post("/{upload_id}/complete", status_code=status.HTTP_202_ACCEPTED)
def complete_upload(upload_id: uuid.UUID, ctx: Ctx = Depends(customer_ctx)) -> UploadOut:
    """Finish the upload and queue validation."""
    upload = upload_domain.get_owned(ctx, me(ctx), upload_id, lock=True)
    upload_domain.complete(ctx, upload)
    ctx.session.commit()
    ctx.session.refresh(upload)
    return upload_out(upload)


@router.delete("/{upload_id}", status_code=status.HTTP_204_NO_CONTENT)
def abort_upload(upload_id: uuid.UUID, ctx: Ctx = Depends(customer_ctx)) -> None:
    upload = upload_domain.get_owned(ctx, me(ctx), upload_id, lock=True)
    upload_domain.abort(ctx, upload)
    ctx.session.commit()
