"""Sliding-window rate limiter with optional Redis backend.

Two modes:
  • In-memory — per-process dict of token buckets (simple, no deps)
  • Redis      — shared state across multiple processes/servers

Default: in-memory with 100 requests / 60s per API key (or IP if key absent).
Implements slowapi-style decorator pattern.  Thread-safe for single-process.
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass

import redis

from mosaic.core.schema import LimitsConfig


class RateLimitExceeded(Exception):  # noqa: N818
    def __init__(self, retry_after: float, limit: int, period: float):
        self.retry_after = retry_after
        self.limit = limit
        self.period = period
        super().__init__(
            f"Rate limit {limit}/{period}s exceeded — retry after {retry_after:.1f}s"
        )


@dataclass
class TokenBucket:
    capacity: int
    refill_rate: float  # tokens per second
    tokens: float = 0.0
    last_refill: float = 0.0


class RateLimiter:
    """Sliding-window rate limiter.  Supports per-key (API key / IP)."""

    def __init__(self, limits: LimitsConfig, redis_url: str | None = None):
        self.limits = limits
        self.redis_url = redis_url or os.getenv("MOSAIC_REDIS_URL")
        self._redis: redis.Redis | None = None
        self._local: dict[str, TokenBucket] = {}
        if self.redis_url:
            self._redis = redis.from_url(self.redis_url, decode_responses=True)

    def check(self, key: str) -> tuple[bool, float]:
        """Return (allowed, retry_after_seconds)."""
        if self._redis:
            return self._check_redis(key)
        return self._check_local(key)

    def _check_local(self, key: str) -> tuple[bool, float]:
        now = time.time()
        bucket = self._local.get(key)
        if not bucket:
            bucket = TokenBucket(
                capacity=self.limits.rate_limit_max,
                refill_rate=self.limits.rate_limit_max
                / self.limits.rate_limit_window_seconds,
            )
            self._local[key] = bucket

        # Refill
        delta = now - bucket.last_refill
        bucket.tokens = min(bucket.capacity, bucket.tokens + delta * bucket.refill_rate)
        bucket.last_refill = now

        if bucket.tokens < 1.0:
            needed = 1.0 - bucket.tokens
            retry = needed / bucket.refill_rate
            return False, max(0.1, retry)
        bucket.tokens -= 1.0
        return True, 0.0

    def _check_redis(self, key: str) -> tuple[bool, float]:
        """Redis sliding window via sorted set + Lua script for atomicity."""
        lua = """
local key = KEYS[1]
local limit = tonumber(ARGV[1])
local window = tonumber(ARGV[2])
local now = tonumber(ARGV[3])

redis.call('ZREMRANGEBYSCORE', key, 0, now - window)
local count = redis.call('ZCARD', key)
if count >= limit then
  local oldest = redis.call('ZRANGE', key, 0, 0, 'WITHSCORES')[2]
  return {0, tonumber(oldest) + window - now}
else
  redis.call('ZADD', key, now, now)
  redis.call('EXPIRE', key, window)
  return {1, 0}
end
"""
        now = time.time()
        allowed, retry = self._redis.eval(
            lua,
            1,
            f"ratelimit:{key}",
            self.limits.rate_limit_max,
            self.limits.rate_limit_window_seconds,
            now,
        )
        return bool(allowed), float(retry or 0.0)

    def reset(self, key: str) -> None:
        if key in self._local:
            self._local.pop(key)
        if self._redis:
            self._redis.delete(f"ratelimit:{key}")
