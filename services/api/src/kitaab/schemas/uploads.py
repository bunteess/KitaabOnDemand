import uuid
from datetime import datetime

from pydantic import Field

from kitaab.domain.enums import UploadRejection, UploadStatus
from kitaab.schemas.common import Schema


class UploadCreate(Schema):
    filename: str = Field(min_length=1, max_length=255)
    size_bytes: int = Field(gt=0)
    client_page_count: int | None = Field(
        default=None, ge=1, description="Page count read on the device; provisional"
    )
    copyright_declared: bool = Field(
        description="The customer confirms they have the right to print this file"
    )


class UploadOut(Schema):
    id: uuid.UUID
    status: UploadStatus
    filename: str | None
    size_bytes: int
    page_count: int | None = Field(description="Authoritative page count from the server")
    client_page_count: int | None
    rejection_code: UploadRejection | None
    rejection_message: str | None
    uploaded_parts: list[int] = Field(
        default_factory=list, description="Part numbers storage already has (while uploading)"
    )
    created_at: datetime
    validated_at: datetime | None


class PartUrl(Schema):
    number: int
    url: str


class UploadSession(Schema):
    upload: UploadOut
    part_size_bytes: int
    part_count: int
    parts: list[PartUrl]
    urls_expire_at: datetime


class PartUrlsRequest(Schema):
    part_numbers: list[int] = Field(min_length=1, max_length=100)


class PartUrls(Schema):
    parts: list[PartUrl]
    urls_expire_at: datetime
