"""Request IDs, access logs, security headers and a request body size limit."""

import logging
import time
import uuid
from collections.abc import Awaitable, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from kitaab.logging import request_id_var

log = logging.getLogger("kitaab.request")

MAX_BODY_BYTES = 1024 * 1024  # JSON only: files go straight to storage


class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        incoming = request.headers.get("x-request-id", "")
        request_id = (
            incoming if 8 <= len(incoming) <= 64 and incoming.isascii() else uuid.uuid4().hex
        )
        token = request_id_var.set(request_id)
        started = time.perf_counter()
        status = 500
        try:
            response = await call_next(request)
            status = response.status_code
            response.headers["X-Request-ID"] = request_id
            return response
        except Exception:
            log.exception("unhandled error", extra={"path": request.url.path})
            raise
        finally:
            # Path only: query strings can carry phone numbers (admin search).
            log.info(
                "request",
                extra={
                    "method": request.method,
                    "path": request.url.path,
                    "status": status,
                    "duration_ms": round((time.perf_counter() - started) * 1000, 1),
                },
            )
            request_id_var.reset(token)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp, *, hsts: bool) -> None:
        super().__init__(app)
        self.hsts = hsts

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        response = await call_next(request)
        headers = response.headers
        headers.setdefault("X-Content-Type-Options", "nosniff")
        headers.setdefault("X-Frame-Options", "DENY")
        headers.setdefault("Referrer-Policy", "no-referrer")
        headers.setdefault("Cross-Origin-Opener-Policy", "same-origin")
        is_html = headers.get("content-type", "").startswith("text/html")
        is_docs = request.url.path in ("/docs", "/openapi.json")
        if not is_html and not is_docs:
            headers.setdefault(
                "Content-Security-Policy", "default-src 'none'; frame-ancestors 'none'"
            )
        if self.hsts:
            headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
        if request.url.path.startswith("/api/"):
            headers.setdefault("Cache-Control", "no-store")
        return response


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

        # Inner BaseHTTPMiddleware task groups wrap the error in an ExceptionGroup.
        try:
            await self.app(scope, limited_receive, tracking_send)
        except* _BodyTooLarge:
            if started:
                raise
            await _too_large()(scope, receive, send)
