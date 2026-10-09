"""Google ID token verification with the official google-auth library (D-029).

Sign in with Apple is deferred with iOS (D-002); an AppleIdTokenVerifier can
implement the same protocol later.
"""

from dataclasses import dataclass
from typing import Any, Protocol


@dataclass(frozen=True)
class ExternalIdentity:
    subject: str
    email: str | None
    name: str | None


class InvalidIdToken(Exception):  # noqa: N818
    pass


class IdTokenVerifier(Protocol):
    def verify(self, token: str) -> ExternalIdentity: ...


class GoogleIdTokenVerifier:
    def __init__(self, client_ids: list[str]) -> None:
        self.client_ids = client_ids

    def verify(self, token: str) -> ExternalIdentity:
        from google.auth.transport import requests
        from google.oauth2 import id_token

        if not self.client_ids:
            raise InvalidIdToken("GOOGLE_OAUTH_CLIENT_IDS is not set")
        try:
            claims: dict[str, Any] = id_token.verify_oauth2_token(  # type: ignore[no-untyped-call]
                token, requests.Request(), audience=None
            )
        except ValueError as exc:
            raise InvalidIdToken(str(exc)) from exc
        if claims.get("aud") not in self.client_ids:
            raise InvalidIdToken("unexpected audience")
        if claims.get("iss") not in ("accounts.google.com", "https://accounts.google.com"):
            raise InvalidIdToken("unexpected issuer")
        return ExternalIdentity(
            subject=str(claims["sub"]),
            email=claims.get("email") if claims.get("email_verified") else None,
            name=claims.get("name"),
        )


class FakeIdTokenVerifier:
    """Accepts "fake-google-<subject>" tokens. Development and tests only."""

    def verify(self, token: str) -> ExternalIdentity:
        if not token.startswith("fake-google-"):
            raise InvalidIdToken("not a fake token")
        subject = token.removeprefix("fake-google-")
        return ExternalIdentity(subject=subject, email=f"{subject}@example.com", name="Google User")
