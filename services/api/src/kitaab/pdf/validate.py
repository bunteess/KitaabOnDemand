"""Server-side PDF checks (brief section 3.3). Runs in the worker on a local copy.

Order of checks: size, magic bytes, MIME sniff, virus scan, open with pikepdf,
encryption, page count, active content. The page count found here is the
authoritative one.
"""

import hashlib
import logging
from dataclasses import dataclass
from pathlib import Path

import magic
import pikepdf

from kitaab.domain.enums import UploadRejection
from kitaab.providers.antivirus import ScanError, VirusScanner

log = logging.getLogger(__name__)

MAGIC = b"%PDF-"
_ACTIVE_KEYS = {"/JS", "/JavaScript", "/EmbeddedFile", "/EmbeddedFiles", "/AA"}
_ACTIVE_ACTIONS = {
    "/JavaScript",
    "/Launch",
    "/ImportData",
    "/SubmitForm",
    "/ResetForm",
    "/Rendition",
    "/GoToE",
}


@dataclass(frozen=True)
class PdfCheck:
    page_count: int | None
    sha256: str | None
    size_bytes: int
    rejection: UploadRejection | None = None
    detail: str | None = None

    @property
    def ok(self) -> bool:
        return self.rejection is None


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _has_active_content(pdf: pikepdf.Pdf) -> str | None:
    """Returns why the file contains scripts, launch actions or attachments."""
    root = pdf.Root
    open_action = root.get("/OpenAction")
    # A destination array just opens a page; an action dictionary runs something.
    if isinstance(open_action, pikepdf.Dictionary):
        action = open_action.get("/S")
        if action is not None and str(action) != "/GoTo":
            return f"OpenAction {action}"
    for obj in pdf.objects:
        if not isinstance(obj, pikepdf.Dictionary | pikepdf.Stream):
            continue
        keys = set(obj.keys())
        found = keys & _ACTIVE_KEYS
        if found:
            return f"contains {sorted(found)[0]}"
        action = obj.get("/S")
        if action is not None and str(action) in _ACTIVE_ACTIONS:
            return f"action {action}"
        if str(obj.get("/Type", "")) in ("/EmbeddedFile", "/Filespec"):
            return "embedded file"
    return None


def validate_pdf(
    path: Path, *, max_bytes: int, scanner: VirusScanner | None = None, require_scan: bool = False
) -> PdfCheck:
    size = path.stat().st_size
    if size > max_bytes:
        return PdfCheck(None, None, size, UploadRejection.TOO_LARGE, f"{size} bytes")
    with path.open("rb") as handle:
        header = handle.read(len(MAGIC))
    if header != MAGIC:
        return PdfCheck(None, None, size, UploadRejection.NOT_PDF, "missing %PDF- header")
    mime = magic.from_file(str(path), mime=True)
    if mime != "application/pdf":
        return PdfCheck(None, None, size, UploadRejection.NOT_PDF, f"sniffed {mime}")
    sha256 = sha256_of(path)

    if scanner is not None:
        try:
            result = scanner.scan_file(path)
        except ScanError as error:
            log.error("virus scan failed", extra={"error": str(error)})
            if require_scan:
                return PdfCheck(
                    None, sha256, size, UploadRejection.SCAN_FAILED, "scanner unavailable"
                )
        else:
            if not result.clean:
                return PdfCheck(None, sha256, size, UploadRejection.MALWARE, result.signature)

    try:
        with pikepdf.open(path) as pdf:
            if pdf.is_encrypted:
                return PdfCheck(None, sha256, size, UploadRejection.ENCRYPTED, "encrypted")
            pages = len(pdf.pages)
            if pages == 0:
                return PdfCheck(0, sha256, size, UploadRejection.NO_PAGES, "no pages")
            reason = _has_active_content(pdf)
            if reason:
                return PdfCheck(pages, sha256, size, UploadRejection.ACTIVE_CONTENT, reason)
    except pikepdf.PasswordError:
        return PdfCheck(None, sha256, size, UploadRejection.ENCRYPTED, "password-protected")
    except (pikepdf.PdfError, ValueError, RuntimeError) as error:
        return PdfCheck(None, sha256, size, UploadRejection.CORRUPT, str(error)[:200])
    return PdfCheck(pages, sha256, size)
