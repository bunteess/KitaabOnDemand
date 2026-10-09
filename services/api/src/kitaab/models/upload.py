import uuid
from datetime import datetime

from sqlalchemy import BigInteger, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from kitaab.db import Base
from kitaab.domain.enums import UploadRejection, UploadStatus
from kitaab.models.base import default_now, enum_column, timestamp, uuid_pk


class Upload(Base):
    """A customer's PDF in object storage. After purge the row stays with the
    page count and hash, and `object_key` is null."""

    __tablename__ = "uploads"

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    status: Mapped[UploadStatus] = mapped_column(enum_column(UploadStatus), index=True)
    object_key: Mapped[str | None] = mapped_column(String(200))
    s3_upload_id: Mapped[str | None] = mapped_column(String(1024))
    filename: Mapped[str | None] = mapped_column(String(255))
    declared_size_bytes: Mapped[int] = mapped_column(BigInteger)
    size_bytes: Mapped[int | None] = mapped_column(BigInteger)
    part_count: Mapped[int] = mapped_column(Integer)
    client_page_count: Mapped[int | None] = mapped_column(Integer)
    page_count: Mapped[int | None] = mapped_column(Integer)
    sha256: Mapped[str | None] = mapped_column(String(64))
    rejection_code: Mapped[UploadRejection | None] = mapped_column(enum_column(UploadRejection))
    copyright_declared_at: Mapped[datetime | None] = timestamp()
    created_at: Mapped[datetime] = default_now()
    completed_at: Mapped[datetime | None] = timestamp()
    validated_at: Mapped[datetime | None] = timestamp()
    purged_at: Mapped[datetime | None] = timestamp()
