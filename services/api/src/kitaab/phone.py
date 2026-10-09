"""Pakistani mobile numbers.

Accepted input forms (spaces, dashes, dots and brackets are ignored):
    03XX XXXXXXX, 3XX XXXXXXX, +92 3XX XXXXXXX, 92 3XX XXXXXXX, 0092 3XX XXXXXXX
Output is E.164: +923XXXXXXXXX.
"""

import re

_SEPARATORS = re.compile(r"[\s\-().]")
_MOBILE = re.compile(r"3\d{9}")


class InvalidPhoneError(ValueError):
    pass


def normalize_pk_mobile(raw: str) -> str:
    digits = _SEPARATORS.sub("", raw.strip())
    if digits.startswith("+92"):
        national = digits[3:]
    elif digits.startswith("0092"):
        national = digits[4:]
    elif digits.startswith("92") and len(digits) == 12:
        national = digits[2:]
    elif digits.startswith("0"):
        national = digits[1:]
    else:
        national = digits
    if not _MOBILE.fullmatch(national):
        raise InvalidPhoneError("Enter a Pakistani mobile number, for example 0300 1234567")
    return "+92" + national


def mask_phone(e164: str | None) -> str:
    """For logs and support views: +923001234567 -> +92300*****67."""
    if not e164:
        return ""
    if len(e164) < 8:
        return "*" * len(e164)
    return e164[:6] + "*" * (len(e164) - 8) + e164[-2:]
