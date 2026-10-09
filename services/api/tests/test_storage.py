"""S3 object store against the MinIO from `make deps-up`."""

import uuid
from pathlib import Path

import httpx2
import pytest

from kitaab.config import Settings
from kitaab.providers.storage import S3ObjectStore

pytestmark = pytest.mark.integration

MB = 1024 * 1024


@pytest.fixture(scope="module")
def store() -> S3ObjectStore:
    s = S3ObjectStore(Settings())
    s.ensure_bucket()
    s.ensure_bucket()  # idempotent
    return s


def test_multipart_upload_through_presigned_urls(store: S3ObjectStore, tmp_path: Path) -> None:
    key = f"uploads/{uuid.uuid4()}.pdf"
    upload_id = store.create_multipart_upload(key, "application/pdf")
    first = b"a" * (5 * MB)  # S3 parts other than the last must be at least 5 MB
    second = b"b" * 1000

    for number, body in ((1, first), (2, second)):
        url = store.presign_upload_part(key, upload_id, number, expires_seconds=300)
        response = httpx2.put(url, content=body)
        assert response.status_code == 200, response.text

    parts = store.list_parts(key, upload_id)
    assert [(p.number, p.size) for p in parts] == [(1, len(first)), (2, len(second))]
    # MinIO lists in-progress uploads only for an exact key, so the purge job works
    # from the upload ids stored in the database rather than listing the bucket.
    assert any(u.upload_id == upload_id for u in store.list_multipart_uploads(key))

    store.complete_multipart_upload(key, upload_id, parts)
    assert store.object_size(key) == len(first) + len(second)

    target = tmp_path / "copy.pdf"
    store.download_to_file(key, target)
    assert target.stat().st_size == len(first) + len(second)

    download_url = store.presign_get(key, 60, "My Book (final).pdf")
    response = httpx2.get(download_url)
    assert response.status_code == 200
    assert 'filename="MyBookfinal.pdf"' in response.headers["content-disposition"]


def test_abort_multipart_upload_is_idempotent(store: S3ObjectStore) -> None:
    key = f"uploads/{uuid.uuid4()}.pdf"
    upload_id = store.create_multipart_upload(key, "application/pdf")
    store.abort_multipart_upload(key, upload_id)
    store.abort_multipart_upload(key, upload_id)
    assert all(u.upload_id != upload_id for u in store.list_multipart_uploads(key))


def test_delete_all_versions_removes_every_version(store: S3ObjectStore) -> None:
    key = f"slips/{uuid.uuid4()}.pdf"
    store.put_bytes(key, b"%PDF-1 first", "application/pdf")
    store.put_bytes(key, b"%PDF-1 second", "application/pdf")
    assert store.delete_all_versions(key) >= 2
    assert store.object_size(key) is None
    assert store.delete_all_versions(key) == 0
