"""PDF uploads: presigned multipart upload to MinIO, then the validation job.

Fixtures are generated in code (tests/support.py): a valid multi-page PDF,
corrupt, encrypted, an executable renamed to .pdf, JavaScript, zero pages and
a sparse file one byte over the 150 MB limit.
"""

import io
import os
from pathlib import Path

import httpx2
import pikepdf
import pytest
from sqlalchemy import select

from kitaab.config import MB
from kitaab.domain.enums import UploadRejection
from kitaab.models import Notification, Upload
from kitaab.pdf.validate import validate_pdf
from kitaab.providers.antivirus import ScanError, ScanResult
from support import (
    Api,
    attachment_pdf_bytes,
    corrupt_pdf_bytes,
    encrypted_pdf_bytes,
    exe_bytes,
    goto_open_action_pdf_bytes,
    javascript_pdf_bytes,
    launch_action_pdf_bytes,
    owner_locked_pdf_bytes,
    pdf_bytes,
    zero_page_pdf_bytes,
)

LIMIT = 150 * MB


def _write(tmp_path: Path, content: bytes, name: str = "file.pdf") -> Path:
    path = tmp_path / name
    path.write_bytes(content)
    return path


# -- the validator --------------------------------------------------------------------


def test_valid_multi_page_pdf(tmp_path: Path) -> None:
    check = validate_pdf(_write(tmp_path, pdf_bytes(12)), max_bytes=LIMIT)
    assert check.ok
    assert check.page_count == 12
    assert check.sha256 is not None
    assert len(check.sha256) == 64


@pytest.mark.parametrize(
    ("content", "rejection"),
    [
        (corrupt_pdf_bytes(), UploadRejection.CORRUPT),
        (encrypted_pdf_bytes(), UploadRejection.ENCRYPTED),
        (owner_locked_pdf_bytes(), UploadRejection.ENCRYPTED),
        (exe_bytes(), UploadRejection.NOT_PDF),
        (javascript_pdf_bytes(), UploadRejection.ACTIVE_CONTENT),
        (launch_action_pdf_bytes(), UploadRejection.ACTIVE_CONTENT),
        (attachment_pdf_bytes(), UploadRejection.ACTIVE_CONTENT),
        (zero_page_pdf_bytes(), UploadRejection.NO_PAGES),
        (b"", UploadRejection.NOT_PDF),
    ],
    ids=[
        "corrupt",
        "encrypted",
        "owner-password",
        "exe-renamed",
        "javascript",
        "launch",
        "attachment",
        "zero-pages",
        "empty",
    ],
)
def test_bad_files_are_rejected(tmp_path: Path, content: bytes, rejection: UploadRejection) -> None:
    check = validate_pdf(_write(tmp_path, content), max_bytes=LIMIT)
    assert check.rejection == rejection
    assert not check.ok


def test_pdf_header_on_another_file_type_is_rejected(tmp_path: Path) -> None:
    # Starts like a PDF but libmagic sees an HTML document.
    content = b"%PDF-<html><head><title>x</title></head><body>" + b"<p>hi</p>" * 200
    check = validate_pdf(_write(tmp_path, content), max_bytes=LIMIT)
    assert check.rejection in (UploadRejection.NOT_PDF, UploadRejection.CORRUPT)


def test_page_jump_open_action_is_allowed(tmp_path: Path) -> None:
    check = validate_pdf(_write(tmp_path, goto_open_action_pdf_bytes()), max_bytes=LIMIT)
    assert check.ok
    assert check.page_count == 2


def test_one_byte_over_the_limit_is_rejected_without_reading(tmp_path: Path) -> None:
    path = tmp_path / "huge.pdf"
    with path.open("wb") as handle:
        handle.truncate(LIMIT + 1)  # sparse: takes no disk space
    check = validate_pdf(path, max_bytes=LIMIT)
    assert check.rejection == UploadRejection.TOO_LARGE
    assert check.size_bytes == LIMIT + 1


class _Scanner:
    def __init__(self, result: ScanResult | None = None, error: bool = False) -> None:
        self.result = result
        self.error = error
        self.scanned: list[Path] = []

    def scan_file(self, path: Path) -> ScanResult:
        self.scanned.append(path)
        if self.error:
            raise ScanError("down")
        assert self.result is not None
        return self.result


def test_malware_found_by_the_scanner(tmp_path: Path) -> None:
    scanner = _Scanner(ScanResult(clean=False, signature="Eicar-Test-Signature"))
    check = validate_pdf(_write(tmp_path, pdf_bytes()), max_bytes=LIMIT, scanner=scanner)
    assert check.rejection == UploadRejection.MALWARE
    assert check.detail == "Eicar-Test-Signature"


def test_clean_scan_continues_to_the_pdf_checks(tmp_path: Path) -> None:
    scanner = _Scanner(ScanResult(clean=True))
    check = validate_pdf(_write(tmp_path, pdf_bytes(2)), max_bytes=LIMIT, scanner=scanner)
    assert check.ok
    assert len(scanner.scanned) == 1


def test_scanner_outage_fails_closed_only_when_required(tmp_path: Path) -> None:
    path = _write(tmp_path, pdf_bytes())
    lenient = validate_pdf(path, max_bytes=LIMIT, scanner=_Scanner(error=True))
    assert lenient.ok
    strict = validate_pdf(path, max_bytes=LIMIT, scanner=_Scanner(error=True), require_scan=True)
    assert strict.rejection == UploadRejection.SCAN_FAILED


# -- the upload pipeline --------------------------------------------------------------


@pytest.mark.integration
def test_valid_upload_becomes_valid_with_the_server_page_count(api: Api) -> None:
    customer = api.customer()
    content = pdf_bytes(7)
    created = api.post(
        "/api/v1/uploads",
        customer,
        {
            "filename": "../../My <Notes>.pdf",
            "size_bytes": len(content),
            "client_page_count": 6,
            "copyright_declared": True,
        },
    ).json()
    assert created["part_count"] == 1
    assert created["upload"]["status"] == "AWAITING_PARTS"
    assert created["upload"]["filename"] == "My Notes.pdf"
    httpx2.put(created["parts"][0]["url"], content=content).raise_for_status()
    upload_id = created["upload"]["id"]
    in_progress = api.get(f"/api/v1/uploads/{upload_id}", customer).json()
    assert in_progress["uploaded_parts"] == [1]

    completed = api.post(f"/api/v1/uploads/{upload_id}/complete", customer)
    assert completed.status_code == 202
    result = api.get(f"/api/v1/uploads/{upload_id}", customer).json()
    assert result["status"] == "VALID"
    assert result["page_count"] == 7
    assert result["client_page_count"] == 6
    assert result["size_bytes"] == len(content)
    with api.services.session() as session:
        upload = session.get(Upload, upload_id)
        assert upload is not None
        assert upload.object_key is not None
        assert api.services.store.object_size(upload.object_key) == len(content)
        inbox = session.scalars(select(Notification.title)).all()
    assert "File ready" in inbox

    # Once validated, the upload is closed.
    again = api.post(f"/api/v1/uploads/{upload_id}/complete", customer)
    assert again.status_code == 409


@pytest.mark.integration
@pytest.mark.parametrize(
    ("content", "code"),
    [
        (javascript_pdf_bytes(), "ACTIVE_CONTENT"),
        (encrypted_pdf_bytes(), "ENCRYPTED"),
        (corrupt_pdf_bytes(), "CORRUPT"),
        (exe_bytes(), "NOT_PDF"),
        (zero_page_pdf_bytes(), "NO_PAGES"),
    ],
    ids=["javascript", "encrypted", "corrupt", "exe", "zero-pages"],
)
def test_rejected_upload_is_deleted_from_storage(api: Api, content: bytes, code: str) -> None:
    customer = api.customer()
    result = api.upload(customer, content, filename="bad.pdf")
    assert result["status"] == "REJECTED"
    assert result["rejection_code"] == code
    assert result["rejection_message"]
    assert result["page_count"] is None
    with api.services.session() as session:
        upload = session.get(Upload, result["id"])
        assert upload is not None
        assert upload.object_key is None
        assert upload.purged_at is not None


@pytest.mark.integration
def test_multipart_upload_and_resume(api: Api) -> None:
    api.services.settings = api.services.settings.model_copy(update={"upload_part_bytes": 5 * MB})
    with pikepdf.open(io.BytesIO(pdf_bytes(3))) as pdf:
        pdf.pages[0].obj.PieceInfo = pikepdf.Dictionary(Pad=pdf.make_stream(os.urandom(6 * MB)))
        buffer = io.BytesIO()
        pdf.save(buffer, compress_streams=False)
    content = buffer.getvalue()
    assert len(content) > 6 * MB

    customer = api.customer()
    created = api.post(
        "/api/v1/uploads",
        customer,
        {"filename": "big.pdf", "size_bytes": len(content), "copyright_declared": True},
    ).json()
    assert created["part_count"] == 2
    upload_id = created["upload"]["id"]
    size = created["part_size_bytes"]
    httpx2.put(created["parts"][0]["url"], content=content[:size]).raise_for_status()

    early = api.post(f"/api/v1/uploads/{upload_id}/complete", customer)
    assert early.status_code == 409
    assert early.json()["extra"]["missing_parts"] == [2]

    # The app comes back later: which parts are there, and fresh URLs for the rest.
    status = api.get(f"/api/v1/uploads/{upload_id}", customer).json()
    assert status["uploaded_parts"] == [1]
    fresh = api.post(f"/api/v1/uploads/{upload_id}/parts", customer, {"part_numbers": [2]}).json()
    httpx2.put(fresh["parts"][0]["url"], content=content[size:]).raise_for_status()

    assert api.post(f"/api/v1/uploads/{upload_id}/complete", customer).status_code == 202
    result = api.get(f"/api/v1/uploads/{upload_id}", customer).json()
    assert result["status"] == "VALID", result
    assert result["page_count"] == 3


@pytest.mark.integration
def test_part_numbers_out_of_range(api: Api) -> None:
    customer = api.customer()
    created = api.post(
        "/api/v1/uploads",
        customer,
        {"filename": "a.pdf", "size_bytes": 1000, "copyright_declared": True},
    ).json()
    response = api.post(
        f"/api/v1/uploads/{created['upload']['id']}/parts", customer, {"part_numbers": [2]}
    )
    assert response.status_code == 422
    assert response.json()["code"] == "invalid-part"


@pytest.mark.integration
def test_uploading_more_than_declared_is_rejected(api: Api) -> None:
    customer = api.customer()
    content = pdf_bytes(2)
    created = api.post(
        "/api/v1/uploads",
        customer,
        {"filename": "a.pdf", "size_bytes": 100, "copyright_declared": True},
    ).json()
    httpx2.put(created["parts"][0]["url"], content=content).raise_for_status()
    upload_id = created["upload"]["id"]
    api.post(f"/api/v1/uploads/{upload_id}/complete", customer)
    result = api.get(f"/api/v1/uploads/{upload_id}", customer).json()
    assert result["status"] == "REJECTED"
    assert result["rejection_code"] == "SIZE_MISMATCH"


@pytest.mark.integration
def test_declared_size_over_the_limit_is_refused(api: Api) -> None:
    customer = api.customer()
    response = api.post(
        "/api/v1/uploads",
        customer,
        {"filename": "a.pdf", "size_bytes": LIMIT + 1, "copyright_declared": True},
    )
    assert response.status_code == 422
    assert response.json()["code"] == "upload-too-large"


@pytest.mark.integration
def test_stored_object_over_the_limit_is_rejected_by_the_worker(api: Api) -> None:
    customer = api.customer()
    api.tasks.eager = False
    result = api.upload(customer, pdf_bytes(2))
    assert result["status"] == "VALIDATING"
    api.services.settings = api.services.settings.model_copy(update={"max_upload_bytes": 100})
    assert api.tasks.run_pending() >= 1
    result = api.get(f"/api/v1/uploads/{result['id']}", customer).json()
    assert result["rejection_code"] == "TOO_LARGE"


@pytest.mark.integration
def test_copyright_declaration_is_required(api: Api) -> None:
    customer = api.customer()
    response = api.post(
        "/api/v1/uploads",
        customer,
        {"filename": "a.pdf", "size_bytes": 1000, "copyright_declared": False},
    )
    assert response.status_code == 422
    assert response.json()["code"] == "copyright-required"


@pytest.mark.integration
def test_abort_upload(api: Api) -> None:
    customer = api.customer()
    created = api.post(
        "/api/v1/uploads",
        customer,
        {"filename": "a.pdf", "size_bytes": 1000, "copyright_declared": True},
    ).json()
    upload_id = created["upload"]["id"]
    assert api.delete(f"/api/v1/uploads/{upload_id}", customer).status_code == 204
    assert api.get(f"/api/v1/uploads/{upload_id}", customer).json()["status"] == "ABORTED"
    assert api.delete(f"/api/v1/uploads/{upload_id}", customer).status_code == 204
    closed = api.post(f"/api/v1/uploads/{upload_id}/parts", customer, {"part_numbers": [1]})
    assert closed.status_code == 409
    assert api.post(f"/api/v1/uploads/{upload_id}/complete", customer).status_code == 409


@pytest.mark.integration
def test_finished_uploads_cannot_be_aborted(api: Api) -> None:
    customer = api.customer()
    result = api.upload(customer)
    response = api.delete(f"/api/v1/uploads/{result['id']}", customer)
    assert response.status_code == 409


@pytest.mark.integration
def test_other_customers_cannot_see_an_upload(api: Api) -> None:
    owner = api.customer()
    result = api.upload(owner)
    stranger = api.customer()
    assert api.get(f"/api/v1/uploads/{result['id']}", stranger).status_code == 404
    assert api.post(f"/api/v1/uploads/{result['id']}/complete", stranger).status_code == 404
    assert api.delete(f"/api/v1/uploads/{result['id']}", stranger).status_code == 404


@pytest.mark.integration
def test_uploads_are_rate_limited(api: Api) -> None:
    customer = api.customer()
    body = {"filename": "a.pdf", "size_bytes": 1000, "copyright_declared": True}
    for _ in range(20):
        assert api.post("/api/v1/uploads", customer, body).status_code == 201
    limited = api.post("/api/v1/uploads", customer, body)
    assert limited.status_code == 429
    assert "Retry-After" in limited.headers
