"""Request IDs, access logs, security headers and a request body size limit."""

import logging
import time
import uuid

from starlette.datastructures import MutableHeaders
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from kitaab.logging import request_id_var

log = logging.getLogger("kitaab.request")

MAX_BODY_BYTES = 1024 * 1024  # JSON only: files go straight to storage


class RequestContextMiddleware:
    """Request ID (from X-Request-ID or new), one access log line per request,
    and a log entry with the traceback for unhandled errors. Plain ASGI: no
    per-request task group, unlike Starlette's BaseHTTPMiddleware."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        headers = dict(scope.get("headers", []))
        incoming = headers.get(b"x-request-id", b"").decode("latin-1")
        request_id = (
            incoming if 8 <= len(incoming) <= 64 and incoming.isascii() else uuid.uuid4().hex
        )
        token = request_id_var.set(request_id)
        started = time.perf_counter()
        status = 500

        async def send_with_id(message: Message) -> None:
            nonlocal status
            if message["type"] == "http.response.start":
                status = message["status"]
                MutableHeaders(scope=message)["X-Request-ID"] = request_id
            await send(message)

        try:
            await self.app(scope, receive, send_with_id)
        except Exception:
            log.exception("unhandled error", extra={"path": scope.get("path", "")})
            raise
        finally:
            # Path only: query strings can carry phone numbers (admin search).
            log.info(
                "request",
                extra={
                    "method": scope.get("method", ""),
                    "path": scope.get("path", ""),
                    "status": status,
                    "duration_ms": round((time.perf_counter() - started) * 1000, 1),
                },
            )
            request_id_var.reset(token)


class SecurityHeadersMiddleware:
    def __init__(self, app: ASGIApp, *, hsts: bool) -> None:
        self.app = app
        self.hsts = hsts

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        path: str = scope.get("path", "")

        async def send_with_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                headers.setdefault("X-Content-Type-Options", "nosniff")
                headers.setdefault("X-Frame-Options", "DENY")
                headers.setdefault("Referrer-Policy", "no-referrer")
                headers.setdefault("Cross-Origin-Opener-Policy", "same-origin")
                is_html = headers.get("content-type", "").startswith("text/html")
                if not is_html and path not in ("/docs", "/openapi.json"):
                    headers.setdefault(
                        "Content-Security-Policy", "default-src 'none'; frame-ancestors 'none'"
                    )
                if self.hsts:
                    headers.setdefault(
                        "Strict-Transport-Security", "max-age=31536000; includeSubDomains"
                    )
                if path.startswith("/api/"):
                    headers.setdefault("Cache-Control", "no-store")
            await send(message)

        await self.app(scope, receive, send_with_headers)


class _BodyTooLarge(Exception):  # noqa: N818
    pass


def _too_large() -> JSONResponse:
    return JSONResponse(
        {
            "type": "https://kitaabondemand.pk/problems/payload-too-large",
            "title": "Request body too large",
            "status": 413,
            "code": "payload-too-large",
        },
        status_code=413,
        media_type="application/problem+json",
    )


class BodySizeLimitMiddleware:
    """Rejects request bodies over MAX_BODY_BYTES, by Content-Length up front
    or while a chunked body is read."""

    def __init__(self, app: ASGIApp, max_bytes: int = MAX_BODY_BYTES) -> None:
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        length = dict(scope.get("headers", [])).get(b"content-length")
        if length is not None and length.isdigit() and int(length) > self.max_bytes:
            await _too_large()(scope, receive, send)
            return
        received = 0
        started = False

        async def limited_receive() -> Message:
            nonlocal received
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > self.max_bytes:
                    raise _BodyTooLarge
            return message

        async def tracking_send(message: Message) -> None:
            nonlocal started
            if message["type"] == "http.response.start":
                started = True
            await send(message)

        # Anything that runs the app in a task group may wrap the error in an
        # ExceptionGroup, so catch both forms.
        try:
            await self.app(scope, limited_receive, tracking_send)
        except* _BodyTooLarge:
            if started:
                raise
            await _too_large()(scope, receive, send)
