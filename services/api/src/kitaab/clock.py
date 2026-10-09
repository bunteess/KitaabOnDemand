"""Time source for everything time-dependent (OTP expiry, quote expiry, purge).

Business functions take a `Clock` argument. Model defaults (created_at) use the
process-wide clock from `current()`, which the app and worker set at start-up
and tests replace with a `FrozenClock`.

`OffsetClock` lets development and end-to-end runs move time forward (for
example "advance 7 days, then run the purge"). The offset lives in Redis so the
API, worker and scheduler agree. It is only used when DEV_TOOLS_ENABLED=true.
"""

import time
from datetime import UTC, datetime, timedelta
from typing import Protocol, cast

import redis

OFFSET_KEY = "kitaab:dev:clock_offset_seconds"


class Clock(Protocol):
    def now(self) -> datetime: ...


class SystemClock:
    def now(self) -> datetime:
        return datetime.now(UTC)


class FrozenClock:
    """For tests: time only moves when told to."""

    def __init__(self, at: datetime) -> None:
        if at.tzinfo is None:
            raise ValueError("FrozenClock needs an aware datetime")
        self._now = at

    def now(self) -> datetime:
        return self._now

    def advance(self, delta: timedelta) -> None:
        self._now += delta

    def set(self, at: datetime) -> None:
        self._now = at


class OffsetClock:
    """System time plus an offset stored in Redis (development and e2e only)."""

    def __init__(self, client: "redis.Redis", cache_seconds: float = 1.0) -> None:
        self._redis = client
        self._cache_seconds = cache_seconds
        self._cached_offset = 0.0
        self._cached_at = 0.0

    def offset_seconds(self) -> float:
        if time.monotonic() - self._cached_at > self._cache_seconds:
            try:
                raw = cast(bytes | None, self._redis.get(OFFSET_KEY))
                self._cached_offset = float(raw) if raw else 0.0
            except redis.RedisError:
                pass  # keep the last known offset
            self._cached_at = time.monotonic()
        return self._cached_offset

    def now(self) -> datetime:
        return datetime.now(UTC) + timedelta(seconds=self.offset_seconds())

    def set_offset(self, seconds: float) -> None:
        self._redis.set(OFFSET_KEY, str(seconds))
        self._cached_offset = seconds
        self._cached_at = time.monotonic()


_current: Clock = SystemClock()


def current() -> Clock:
    return _current


def install(clock: Clock) -> None:
    global _current
    _current = clock


def utcnow() -> datetime:
    """Model default for created_at and similar columns."""
    return _current.now()
