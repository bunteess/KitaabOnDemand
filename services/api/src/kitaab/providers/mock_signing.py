"""HMAC signing shared by the mock gateway and courier, so mock webhooks are
verified exactly like real ones."""

import hashlib
import hmac
import time

SIGNATURE_HEADER = "x-mock-signature"
TIMESTAMP_HEADER = "x-mock-timestamp"
MAX_SKEW_SECONDS = 300


def sign(secret: str, body: bytes, timestamp: int | None = None) -> dict[str, str]:
    ts = str(timestamp if timestamp is not None else int(time.time()))
    digest = hmac.new(secret.encode(), ts.encode() + b"." + body, hashlib.sha256).hexdigest()
    return {SIGNATURE_HEADER: digest, TIMESTAMP_HEADER: ts}


def verify(secret: str, headers: dict[str, str], body: bytes, now: float | None = None) -> bool:
    lowered = {k.lower(): v for k, v in headers.items()}
    signature = lowered.get(SIGNATURE_HEADER, "")
    ts = lowered.get(TIMESTAMP_HEADER, "")
    if not ts.isdigit():
        return False
    if abs((now if now is not None else time.time()) - int(ts)) > MAX_SKEW_SECONDS:
        return False
    expected = hmac.new(secret.encode(), ts.encode() + b"." + body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)
