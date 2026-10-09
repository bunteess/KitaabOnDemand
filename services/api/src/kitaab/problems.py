"""RFC 7807 problem responses.

Every error the API returns has `Content-Type: application/problem+json` and
the fields type, title, status, detail and a machine-readable `code`. Clients
switch on `code`, never on the human-readable text.
"""

import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.exc import OperationalError as SqlOperationalError
from sqlalchemy.exc import TimeoutError as SqlTimeout
from starlette.exceptions import HTTPException as StarletteHTTPException

log = logging.getLogger(__name__)

PROBLEM_BASE = "https://kitaabondemand.pk/problems/"
PROBLEM_MEDIA_TYPE = "application/problem+json"


class FieldError(BaseModel):
    field: str
    message: str


class Problem(BaseModel):
    """Error body (RFC 7807)."""

    type: str
    title: str
    status: int
    detail: str | None = None
    instance: str | None = None
    code: str
    errors: list[FieldError] | None = None
    extra: dict[str, Any] | None = None


class ProblemError(Exception):
    """Raise anywhere to return a problem response."""

    def __init__(
        self,
        status: int,
        code: str,
        title: str,
        detail: str | None = None,
        *,
        extra: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        super().__init__(detail or title)
        self.status = status
        self.code = code
        self.title = title
        self.detail = detail
        self.extra = extra
        self.headers = headers


def not_found(what: str = "Resource") -> ProblemError:
    return ProblemError(404, "not-found", f"{what} not found")


def forbidden(detail: str | None = None) -> ProblemError:
    return ProblemError(403, "forbidden", "You do not have access to this resource", detail)


def unauthorized(detail: str | None = None) -> ProblemError:
    return ProblemError(
        401,
        "unauthorized",
        "Authentication required",
        detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


def conflict(code: str, title: str, detail: str | None = None, **extra: Any) -> ProblemError:
    return ProblemError(409, code, title, detail, extra=extra or None)


def invalid(code: str, title: str, detail: str | None = None, **extra: Any) -> ProblemError:
    return ProblemError(422, code, title, detail, extra=extra or None)


def not_implemented() -> ProblemError:
    return ProblemError(501, "not-implemented", "This endpoint is not implemented yet")


def _body(problem: Problem) -> dict[str, Any]:
    return problem.model_dump(exclude_none=True)


def problem_response(
    request: Request,
    status: int,
    code: str,
    title: str,
    detail: str | None = None,
    *,
    errors: list[FieldError] | None = None,
    extra: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    problem = Problem(
        type=PROBLEM_BASE + code,
        title=title,
        status=status,
        detail=detail,
        instance=request.url.path,
        code=code,
        errors=errors,
        extra=extra,
    )
    return JSONResponse(
        _body(problem), status_code=status, media_type=PROBLEM_MEDIA_TYPE, headers=headers
    )


_STATUS_CODES = {
    400: ("bad-request", "Bad request"),
    401: ("unauthorized", "Authentication required"),
    403: ("forbidden", "You do not have access to this resource"),
    404: ("not-found", "Not found"),
    405: ("method-not-allowed", "Method not allowed"),
    413: ("payload-too-large", "Request body too large"),
    429: ("rate-limited", "Too many requests"),
}


def install_problem_handlers(app: FastAPI) -> None:
    @app.exception_handler(ProblemError)
    async def _problem(request: Request, exc: ProblemError) -> JSONResponse:
        return problem_response(
            request,
            exc.status,
            exc.code,
            exc.title,
            exc.detail,
            extra=exc.extra,
            headers=exc.headers,
        )

    @app.exception_handler(RequestValidationError)
    async def _validation(request: Request, exc: RequestValidationError) -> JSONResponse:
        errors = [
            FieldError(
                field=".".join(str(p) for p in err.get("loc", ()) if p not in ("body", "query")),
                message=str(err.get("msg", "Invalid value")),
            )
            for err in exc.errors()
        ]
        return problem_response(
            request, 422, "validation-error", "Some fields are invalid", errors=errors
        )

    @app.exception_handler(StarletteHTTPException)
    async def _http(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        code, title = _STATUS_CODES.get(exc.status_code, ("error", "Request failed"))
        detail = exc.detail if isinstance(exc.detail, str) and exc.detail != title else None
        return problem_response(
            request, exc.status_code, code, title, detail, headers=getattr(exc, "headers", None)
        )

    @app.exception_handler(SqlTimeout)
    @app.exception_handler(SqlOperationalError)
    async def _busy(request: Request, exc: Exception) -> JSONResponse:
        # Every database connection is in use (overload) or the database is
        # unreachable: ask clients to retry shortly instead of failing hard.
        log.warning("database unavailable", extra={"error": type(exc).__name__})
        return problem_response(
            request,
            503,
            "service-busy",
            "The service is busy. Please try again in a moment.",
            headers={"Retry-After": "5"},
        )

    @app.exception_handler(Exception)
    async def _unexpected(request: Request, exc: Exception) -> JSONResponse:
        # Logged by the request middleware with the request id; never leak internals.
        return problem_response(request, 500, "internal-error", "Something went wrong")


# Shared OpenAPI response declarations so every route documents its errors.
PROBLEM_RESPONSES: dict[int | str, dict[str, Any]] = {
    status: {"model": Problem, "content": {PROBLEM_MEDIA_TYPE: {}}, "description": title}
    for status, (_, title) in {
        **_STATUS_CODES,
        409: ("conflict", "Conflict with the current state"),
        422: ("validation-error", "Validation failed"),
    }.items()
    if status in (400, 401, 403, 404, 409, 422, 429)
}


def file_response(media_type: str, description: str) -> dict[int | str, dict[str, Any]]:
    """OpenAPI declaration for routes that return a file instead of JSON."""
    return {200: {"content": {media_type: {}}, "description": description}}


PDF_RESPONSE = file_response("application/pdf", "PDF document")
CSV_RESPONSE = file_response("text/csv", "CSV export")
