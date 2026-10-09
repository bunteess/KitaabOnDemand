"""Fixed-window rate limits in Redis."""

from dataclasses import dataclass

import redis


@dataclass(frozen=True)
class Limit:
    max_hits: int
    window_seconds: int


class RateLimiter:
    def __init__(self, client: "redis.Redis", prefix: str = "kitaab:rl:") -> None:
        self._redis = client
        self._prefix = prefix

    def hit(self, key: str, limit: Limit) -> int | None:
        """Count one hit. Returns None when allowed, else seconds until the window resets."""
        full = self._prefix + key
        pipe = self._redis.pipeline()
        pipe.incr(full)
        pipe.ttl(full)
        count, ttl = pipe.execute()
        if ttl < 0:
            self._redis.expire(full, limit.window_seconds)
            ttl = limit.window_seconds
        if int(count) > limit.max_hits:
            return max(1, int(ttl))
        return None

    def reset(self, key: str) -> None:
        self._redis.delete(self._prefix + key)
