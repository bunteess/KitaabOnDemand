"""Access tokens (JWT, 15 minutes) and rotating refresh tokens (stored hashed)."""

import hashlib
import secrets
import uuid
from datetime import datetime, timedelta
from typing import Any

import jwt

ALGORITHM = "HS256"
ISSUER = "kitaab-api"
IAT_LEEWAY_SECONDS = 60


def make_access_token(
    user_id: uuid.UUID, role: str, secret: str, now: datetime, ttl: timedelta
) -> str:
    claims = {
        "sub": str(user_id),
        "role": role,
        "typ": "access",
        "iss": ISSUER,
        "iat": int(now.timestamp()),
        "exp": int((now + ttl).timestamp()),
        "jti": uuid.uuid4().hex,
    }
    return jwt.encode(claims, secret, algorithm=ALGORITHM)


class InvalidToken(Exception):  # noqa: N818
    pass


def decode_access_token(token: str, secret: str, now: datetime) -> dict[str, Any]:
    try:
        claims: dict[str, Any] = jwt.decode(
            token,
            secret,
            algorithms=[ALGORITHM],
            issuer=ISSUER,
            options={
                "require": ["exp", "sub", "iat"],
                "verify_exp": False,
                "verify_iat": False,
                "verify_nbf": False,
            },
        )
    except jwt.PyJWTError as exc:
        raise InvalidToken(str(exc)) from exc
    # Times are checked against the injected clock, not the system clock, so
    # tests and the development clock offset can move time.
    current = int(now.timestamp())
    if claims.get("typ") != "access" or int(claims["exp"]) <= current:
        raise InvalidToken("expired or wrong type")
    if int(claims["iat"]) > current + IAT_LEEWAY_SECONDS:
        raise InvalidToken("issued in the future")
    return claims


def new_refresh_token() -> str:
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()
