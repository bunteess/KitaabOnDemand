"""TOTP for admins. Secrets are encrypted at rest with DATA_ENCRYPTION_KEY."""

import base64
import hashlib
from datetime import datetime

import pyotp
from cryptography.fernet import Fernet, InvalidToken

ISSUER = "KitaabOnDemand"


def _fernet(key: str) -> Fernet:
    # Accept any configured string: derive a valid 32-byte Fernet key from it.
    return Fernet(base64.urlsafe_b64encode(hashlib.sha256(key.encode()).digest()))


def new_secret() -> str:
    return pyotp.random_base32()


def encrypt(secret: str, key: str) -> str:
    return _fernet(key).encrypt(secret.encode()).decode()


def decrypt(token: str, key: str) -> str | None:
    try:
        return _fernet(key).decrypt(token.encode()).decode()
    except InvalidToken:
        return None


def provisioning_uri(secret: str, email: str) -> str:
    return pyotp.TOTP(secret).provisioning_uri(name=email, issuer_name=ISSUER)


def verify(secret: str, code: str, at: datetime) -> bool:
    """Accepts the current code and one step either side for clock drift."""
    return pyotp.TOTP(secret).verify(code, for_time=at, valid_window=1)


def code_at(secret: str, at: datetime) -> str:
    return pyotp.TOTP(secret).at(at)
