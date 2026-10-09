"""Authorisation matrix: every route declares exactly one guard, the guard
matches the route's area, and every protected route refuses anonymous callers
(401) and the wrong roles (403)."""

import re
import uuid
from dataclasses import dataclass
from typing import Any

import pytest
from fastapi.dependencies.models import Dependant
from fastapi.routing import APIRoute, iter_route_contexts

from kitaab.config import Settings
from kitaab.main import create_app
from kitaab.security import deps
from support import Api, Person

GUARDS: dict[Any, str] = {
    deps.public_ctx: "public",
    deps.user_ctx: "user",
    deps.customer_ctx: "customer",
    deps.admin_ctx: "admin",
    deps.vendor_ctx: "vendor",
    deps.staff_ctx: "staff",
}
ALLOWED = {
    "user": {"customer", "admin", "vendor"},
    "customer": {"customer"},
    "admin": {"admin"},
    "vendor": {"vendor"},
    "staff": {"admin", "vendor"},
}
# Routes with no session at all: static legal text and health checks, plus the
# development helpers that production never mounts.
UNGUARDED = re.compile(r"^(/healthz|/readyz|/api/v1/legal/\{doc\}|/api/v1/_dev/.*|/mock/.*)$")


def _guards(dependant: Dependant) -> set[str]:
    found: set[str] = set()
    for sub in dependant.dependencies:
        if sub.call in GUARDS:
            found.add(GUARDS[sub.call])  # guards depend on each other: stop here
        else:
            found |= _guards(sub)
    return found


def _expected(path: str) -> str:
    if UNGUARDED.match(path):
        return "none"
    if path.startswith("/api/v1/admin/"):
        return "admin"
    if path.startswith("/api/v1/vendor/"):
        return "vendor"
    if path in ("/api/v1/me", "/api/v1/me/terms"):
        return "user"
    if path.startswith(
        ("/api/v1/me", "/api/v1/orders", "/api/v1/uploads", "/api/v1/notifications")
    ):
        return "customer"
    if path.startswith(
        (
            "/api/v1/auth/",
            "/api/v1/webhooks/",
            "/api/v1/cities",
            "/api/v1/pricing/",
            "/api/v1/app/",
        )
    ):
        return "public"
    raise AssertionError(f"no rule for {path}: add one to this test")


@dataclass(frozen=True)
class Route:
    method: str
    path: str
    dependant: Dependant


def _routes(settings: Settings) -> list[Route]:
    """Every API route with its full path (included routers are nested)."""
    routes = []
    for context in iter_route_contexts(create_app(settings=settings).routes):
        original = context.original_route
        if isinstance(original, APIRoute) and context.path:
            for method in sorted(context.methods or ()):
                routes.append(Route(method, context.path, original.dependant))
    return routes


ROUTES = _routes(Settings())


def test_every_route_has_the_expected_guard() -> None:
    wrong = []
    for route in ROUTES:
        found = _guards(route.dependant)
        expected = _expected(route.path)
        actual = next(iter(found)) if len(found) == 1 else ("none" if not found else str(found))
        if actual != expected:
            wrong.append(f"{route.method} {route.path}: {actual}, expected {expected}")
    assert not wrong, "\n".join(wrong)


def test_the_matrix_covers_every_area() -> None:
    counts: dict[str, int] = {}
    for route in ROUTES:
        counts[_expected(route.path)] = counts.get(_expected(route.path), 0) + 1
    assert counts["admin"] > 40
    assert counts["vendor"] == 6
    assert counts["customer"] > 20
    assert counts["public"] >= 10


def test_production_mounts_no_development_routes() -> None:
    settings = Settings(
        dev_tools_enabled=False, payment_providers=["easypaisa"], courier_providers=["trax"]
    )
    paths = {r.path for r in _routes(settings)}
    assert "/api/v1/orders" in paths
    assert not [p for p in paths if p.startswith(("/api/v1/_dev", "/mock"))]


def _url(path: str) -> str:
    return re.sub(r"\{[^}]+\}", lambda _: str(uuid.uuid4()), path)


@pytest.mark.integration
def test_protected_routes_refuse_anonymous_and_wrong_roles(api: Api) -> None:
    people: dict[str, Person] = {
        "customer": api.customer(),
        "admin": api.admin(),
        "vendor": api.vendor_user(api.vendor()),
    }
    failures = []
    checked = 0
    for route in ROUTES:
        method = route.method
        guard = _expected(route.path)
        if guard in ("public", "none"):
            continue
        url = _url(route.path)
        body = None if method in ("GET", "DELETE") else {}
        anonymous = api.client.request(method, url, json=body)
        if anonymous.status_code != 401:
            failures.append(f"{method} {route.path} anonymous: {anonymous.status_code}")
        for role, person in people.items():
            response = api.client.request(method, url, json=body, headers=person.headers)
            allowed = role in ALLOWED[guard]
            refused = response.status_code in (401, 403)
            if allowed == refused:
                failures.append(f"{method} {route.path} as {role}: {response.status_code}")
            checked += 1
    assert not failures, "\n".join(failures)
    assert checked > 200


@pytest.mark.integration
def test_vendor_login_without_a_vendor_is_refused(api: Api) -> None:
    from kitaab.models import User

    person = api.vendor_user(api.vendor())
    with api.services.session() as session:
        user = session.get(User, person.id)
        assert user is not None
        user.vendor_id = None
        session.commit()
    response = api.get("/api/v1/vendor/orders", person)
    assert response.status_code == 403
