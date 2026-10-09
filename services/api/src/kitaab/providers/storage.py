"""Object storage: S3 in production, MinIO locally. Both speak the S3 API via boto3.

The bucket is private. Clients only ever receive short-lived presigned URLs.
Presigned URLs are signed against S3_PUBLIC_ENDPOINT_URL when set, because the
signature covers the host name and the app reaches MinIO by a different host
than the API does inside Docker.
"""

import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Protocol

import boto3
from botocore.client import Config
from botocore.exceptions import ClientError

from kitaab.config import Settings

if TYPE_CHECKING:
    from mypy_boto3_s3 import S3Client
    from mypy_boto3_s3.type_defs import ObjectIdentifierTypeDef

log = logging.getLogger(__name__)

ABORT_INCOMPLETE_MULTIPART_DAYS = 2


@dataclass(frozen=True)
class UploadedPart:
    number: int
    size: int
    etag: str


@dataclass(frozen=True)
class MultipartUploadInfo:
    key: str
    upload_id: str
    initiated: datetime


class ObjectStore(Protocol):
    def ensure_bucket(self) -> None: ...
    def create_multipart_upload(self, key: str, content_type: str) -> str: ...
    def presign_upload_part(
        self, key: str, upload_id: str, part_number: int, expires_seconds: int
    ) -> str: ...
    def list_parts(self, key: str, upload_id: str) -> list[UploadedPart]: ...
    def complete_multipart_upload(
        self, key: str, upload_id: str, parts: list[UploadedPart]
    ) -> None: ...
    def abort_multipart_upload(self, key: str, upload_id: str) -> None: ...
    def list_multipart_uploads(self, prefix: str = "") -> list[MultipartUploadInfo]: ...
    def object_size(self, key: str) -> int | None: ...
    def download_to_file(self, key: str, path: Path) -> None: ...
    def put_bytes(self, key: str, data: bytes, content_type: str) -> None: ...
    def presign_get(self, key: str, expires_seconds: int, download_name: str) -> str: ...
    def delete_all_versions(self, key: str) -> int: ...


class S3ObjectStore:
    def __init__(self, settings: Settings) -> None:
        self.bucket = settings.s3_bucket
        self._strict = settings.is_production
        config = Config(
            signature_version="s3v4",
            s3={"addressing_style": "path"},
            retries={"max_attempts": 5, "mode": "standard"},
        )
        self._client: S3Client = boto3.client(
            "s3",
            region_name=settings.s3_region,
            endpoint_url=settings.s3_endpoint_url,
            config=config,
        )
        public_endpoint = settings.s3_public_endpoint_url or settings.s3_endpoint_url
        self._presign_client: S3Client = boto3.client(
            "s3",
            region_name=settings.s3_region,
            endpoint_url=public_endpoint,
            config=config,
        )

    # -- bucket setup -------------------------------------------------------

    def ensure_bucket(self) -> None:
        """Create the bucket if needed and apply the security settings.

        Production buckets are created by Terraform; this is for development
        and tests. Settings MinIO does not support are logged and skipped
        outside production.
        """
        try:
            self._client.head_bucket(Bucket=self.bucket)
        except ClientError:
            self._client.create_bucket(Bucket=self.bucket)
        self._apply(
            "versioning",
            lambda: self._client.put_bucket_versioning(
                Bucket=self.bucket, VersioningConfiguration={"Status": "Enabled"}
            ),
        )
        self._apply(
            "encryption",
            lambda: self._client.put_bucket_encryption(
                Bucket=self.bucket,
                ServerSideEncryptionConfiguration={
                    "Rules": [{"ApplyServerSideEncryptionByDefault": {"SSEAlgorithm": "AES256"}}]
                },
            ),
        )
        self._apply(
            "public access block",
            lambda: self._client.put_public_access_block(
                Bucket=self.bucket,
                PublicAccessBlockConfiguration={
                    "BlockPublicAcls": True,
                    "IgnorePublicAcls": True,
                    "BlockPublicPolicy": True,
                    "RestrictPublicBuckets": True,
                },
            ),
        )
        self._apply(
            "lifecycle",
            lambda: self._client.put_bucket_lifecycle_configuration(
                Bucket=self.bucket,
                LifecycleConfiguration={
                    "Rules": [
                        {
                            "ID": "abort-incomplete-multipart",
                            "Status": "Enabled",
                            "Filter": {"Prefix": ""},
                            "AbortIncompleteMultipartUpload": {
                                "DaysAfterInitiation": ABORT_INCOMPLETE_MULTIPART_DAYS
                            },
                        }
                    ]
                },
            ),
        )

    def _apply(self, what: str, action: Any) -> None:
        try:
            action()
        except ClientError as exc:
            if self._strict:
                raise
            log.warning("storage: could not apply %s: %s", what, exc.response.get("Error", {}))

    # -- multipart upload ---------------------------------------------------

    def create_multipart_upload(self, key: str, content_type: str) -> str:
        response = self._client.create_multipart_upload(
            Bucket=self.bucket,
            Key=key,
            ContentType=content_type,
            ServerSideEncryption="AES256",
        )
        return response["UploadId"]

    def presign_upload_part(
        self, key: str, upload_id: str, part_number: int, expires_seconds: int
    ) -> str:
        return self._presign_client.generate_presigned_url(
            "upload_part",
            Params={
                "Bucket": self.bucket,
                "Key": key,
                "UploadId": upload_id,
                "PartNumber": part_number,
            },
            ExpiresIn=expires_seconds,
        )

    def list_parts(self, key: str, upload_id: str) -> list[UploadedPart]:
        parts: list[UploadedPart] = []
        marker = 0
        while True:
            response = self._client.list_parts(
                Bucket=self.bucket,
                Key=key,
                UploadId=upload_id,
                PartNumberMarker=marker,
            )
            for part in response.get("Parts", []):
                parts.append(UploadedPart(part["PartNumber"], part["Size"], part["ETag"]))
            if not response.get("IsTruncated"):
                return parts
            marker = response["NextPartNumberMarker"]

    def complete_multipart_upload(
        self, key: str, upload_id: str, parts: list[UploadedPart]
    ) -> None:
        self._client.complete_multipart_upload(
            Bucket=self.bucket,
            Key=key,
            UploadId=upload_id,
            MultipartUpload={
                "Parts": [
                    {"PartNumber": p.number, "ETag": p.etag}
                    for p in sorted(parts, key=lambda p: p.number)
                ]
            },
        )

    def abort_multipart_upload(self, key: str, upload_id: str) -> None:
        try:
            self._client.abort_multipart_upload(Bucket=self.bucket, Key=key, UploadId=upload_id)
        except ClientError as exc:
            if exc.response.get("Error", {}).get("Code") != "NoSuchUpload":
                raise

    def list_multipart_uploads(self, prefix: str = "") -> list[MultipartUploadInfo]:
        response = self._client.list_multipart_uploads(Bucket=self.bucket, Prefix=prefix)
        return [
            MultipartUploadInfo(u["Key"], u["UploadId"], u["Initiated"])
            for u in response.get("Uploads", [])
        ]

    # -- objects ------------------------------------------------------------

    def object_size(self, key: str) -> int | None:
        try:
            return self._client.head_object(Bucket=self.bucket, Key=key)["ContentLength"]
        except ClientError as exc:
            if exc.response.get("Error", {}).get("Code") in {"404", "NoSuchKey", "NotFound"}:
                return None
            raise

    def download_to_file(self, key: str, path: Path) -> None:
        self._client.download_file(self.bucket, key, str(path))

    def put_bytes(self, key: str, data: bytes, content_type: str) -> None:
        self._client.put_object(
            Bucket=self.bucket,
            Key=key,
            Body=data,
            ContentType=content_type,
            ServerSideEncryption="AES256",
        )

    def presign_get(self, key: str, expires_seconds: int, download_name: str) -> str:
        safe_name = "".join(c for c in download_name if c.isalnum() or c in "._-") or "file.pdf"
        return self._presign_client.generate_presigned_url(
            "get_object",
            Params={
                "Bucket": self.bucket,
                "Key": key,
                "ResponseContentDisposition": f'attachment; filename="{safe_name}"',
            },
            ExpiresIn=expires_seconds,
        )

    def delete_all_versions(self, key: str) -> int:
        """Delete every version and delete marker of a key. Returns the number removed."""
        deleted = 0
        paginator = self._client.get_paginator("list_object_versions")
        for page in paginator.paginate(Bucket=self.bucket, Prefix=key):
            items: list[ObjectIdentifierTypeDef] = [
                {"Key": v["Key"], "VersionId": v["VersionId"]}
                for v in [*page.get("Versions", []), *page.get("DeleteMarkers", [])]
                if v["Key"] == key
            ]
            if items:
                self._client.delete_objects(
                    Bucket=self.bucket, Delete={"Objects": items, "Quiet": True}
                )
                deleted += len(items)
        return deleted
