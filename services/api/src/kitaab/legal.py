"""Legal text shown in the app. PLACEHOLDERS: the owner must replace these
before launch (docs/OWNER_TODO.md)."""

from typing import Literal

from kitaab.config import get_settings
from kitaab.schemas.catalog import LegalDocument

Doc = Literal["terms", "privacy", "copyright"]

_TEXT: dict[str, tuple[str, str]] = {
    "terms": (
        "Terms of Service",
        "PLACEHOLDER. This text must be replaced by the owner's legal terms before launch.\n\n"
        "KitaabOnDemand finds books on request and prints PDFs that customers upload. Prices are shown "
        "before you order. Quotes are valid for the time shown.\n\n"
        "You may cancel an order until it is sent for printing (or, for book requests, until we start "
        "getting the book). Paid amounts for cancelled orders are refunded.",
    ),
    "privacy": (
        "Privacy Policy",
        "PLACEHOLDER. This text must be replaced by the owner's privacy policy before launch.\n\n"
        "We store your mobile number, name and delivery addresses to deliver your orders. Uploaded PDFs are "
        "deleted automatically 7 days after delivery. You can delete your account in the app at any time; "
        "payment records are kept without your personal details.",
    ),
    "copyright": (
        "Copyright declaration",
        "PLACEHOLDER. By uploading a file you confirm that you own it or have permission to print it. "
        "We may refuse files that appear to infringe copyright.",
    ),
}


def document(doc: Doc) -> LegalDocument:
    title, body = _TEXT[doc]
    return LegalDocument(doc=doc, version=get_settings().terms_version, title=title, body=body)
