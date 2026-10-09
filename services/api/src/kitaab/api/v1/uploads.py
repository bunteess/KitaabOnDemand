import uuid

from fastapi import APIRouter, status

from kitaab.problems import not_implemented
from kitaab.schemas.uploads import PartUrls, PartUrlsRequest, UploadCreate, UploadOut, UploadSession

router = APIRouter(prefix="/uploads", tags=["uploads"])


@router.post("", status_code=status.HTTP_201_CREATED)
def create_upload(body: UploadCreate) -> UploadSession:
    """Start a resumable upload. Returns presigned URLs for every 8 MB part."""
    raise not_implemented()


@router.get("/{upload_id}")
def get_upload(upload_id: uuid.UUID) -> UploadOut:
    """Status, validation result and, while uploading, the parts storage already has."""
    raise not_implemented()


@router.post("/{upload_id}/parts")
def get_part_urls(upload_id: uuid.UUID, body: PartUrlsRequest) -> PartUrls:
    """Fresh presigned URLs for the given parts, used when resuming."""
    raise not_implemented()


@router.post("/{upload_id}/complete", status_code=status.HTTP_202_ACCEPTED)
def complete_upload(upload_id: uuid.UUID) -> UploadOut:
    """Finish the upload and queue validation."""
    raise not_implemented()


@router.delete("/{upload_id}", status_code=status.HTTP_204_NO_CONTENT)
def abort_upload(upload_id: uuid.UUID) -> None:
    raise not_implemented()
