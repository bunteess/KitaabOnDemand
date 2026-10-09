"""FastAPI dependencies: database session, services and the signed-in user.

Every route declares exactly one of `public_ctx`, `customer_ctx`, `admin_ctx`,
`vendor_ctx` or `staff_ctx`. The authorisation test matrix checks each route's
choice (tests/test_authz_matrix.py).
"""

import uuid
from collections.abc import Iterator

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from kitaab.container import Services
from kitaab.domain.context import Ctx
from kitaab.domain.enums import Role
from kitaab.models import User
from kitaab.problems import ProblemError, forbidden, unauthorized
from kitaab.security.tokens import InvalidToken, decode_access_token

bearer = HTTPBearer(
    auto_error=False, description="Access token from /auth/otp/verify or /auth/staff/login"
)


def get_services(request: Request) -> Services:
    services: Services = request.app.state.services
    return services


def get_session(services: Services = Depends(get_services)) -> Iterator[Session]:
    session = services.session()
    try:
        yield session
    finally:
        session.close()


def public_ctx(
    session: Session = Depends(get_session), services: Services = Depends(get_services)
) -> Ctx:
    return Ctx(session, services)


def _authenticate(ctx: Ctx, credentials: HTTPAuthorizationCredentials | None) -> User:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise unauthorized()
    secret = ctx.services.settings.jwt_secret.get_secret_value()
    try:
        claims = decode_access_token(credentials.credentials, secret, ctx.now)
        user_id = uuid.UUID(claims["sub"])
    except (InvalidToken, ValueError, KeyError) as error:
        raise ProblemError(
            401, "invalid-token", "Your session has expired", headers={"WWW-Authenticate": "Bearer"}
        ) from error
    user = ctx.session.get(User, user_id)
    if user is None or not user.is_active or user.deleted_at is not None:
        raise ProblemError(
            401, "invalid-token", "Your session has expired", headers={"WWW-Authenticate": "Bearer"}
        )
    ctx.user = user
    return user


def user_ctx(
    ctx: Ctx = Depends(public_ctx),
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
) -> Ctx:
    _authenticate(ctx, credentials)
    return ctx


def _role(ctx: Ctx, *roles: Role) -> Ctx:
    if ctx.user is None or ctx.user.role not in roles:
        raise forbidden()
    return ctx


def customer_ctx(ctx: Ctx = Depends(user_ctx)) -> Ctx:
    return _role(ctx, Role.CUSTOMER)


def admin_ctx(ctx: Ctx = Depends(user_ctx)) -> Ctx:
    return _role(ctx, Role.ADMIN)


def vendor_ctx(ctx: Ctx = Depends(user_ctx)) -> Ctx:
    if ctx.user is not None and ctx.user.role == Role.VENDOR and ctx.user.vendor_id is None:
        raise forbidden("This login is not linked to a vendor")
    return _role(ctx, Role.VENDOR)


def staff_ctx(ctx: Ctx = Depends(user_ctx)) -> Ctx:
    return _role(ctx, Role.ADMIN, Role.VENDOR)


def client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


def me(ctx: Ctx) -> User:
    """The signed-in user of an authenticated context."""
    if ctx.user is None:
        raise unauthorized()
    return ctx.user
