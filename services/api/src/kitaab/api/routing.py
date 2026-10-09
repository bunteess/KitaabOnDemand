"""Route class for the API: database connections are held only while a
request thread is running.

A sync endpoint runs on a request thread, then FastAPI validates its response
on another hop through the thread pool. If the session still held its
connection between those hops, a busy server would run out of connections
while requests waited for threads, and stall (docs/PERF.md). So the session
is closed as the endpoint's last step, on its own thread. The objects it
returned keep their loaded data (expire_on_commit=False).
"""

import functools
import inspect
from collections.abc import Callable
from typing import Any

from fastapi import APIRouter
from fastapi.routing import APIRoute

from kitaab.domain.context import Ctx


def _closing_sessions(endpoint: Callable[..., Any]) -> Callable[..., Any]:
    @functools.wraps(endpoint)
    def run(*args: Any, **kwargs: Any) -> Any:
        try:
            return endpoint(*args, **kwargs)
        finally:
            for value in kwargs.values():
                if isinstance(value, Ctx):
                    value.session.close()

    return run


class SessionReleasingRoute(APIRoute):
    def __init__(self, path: str, endpoint: Callable[..., Any], **kwargs: Any) -> None:
        if not inspect.iscoroutinefunction(endpoint):
            endpoint = _closing_sessions(endpoint)
        super().__init__(path, endpoint, **kwargs)


def api_router(**kwargs: Any) -> APIRouter:
    """An APIRouter whose routes release database connections early."""
    return APIRouter(route_class=SessionReleasingRoute, **kwargs)
