"""CircuitBreaker + with_retry decorator for fault tolerance."""

from __future__ import annotations

import asyncio
import functools
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import ParamSpec, TypeVar

T = TypeVar("T")
P = ParamSpec("P")


class CircuitBreakerError(RuntimeError):
    pass


@dataclass
class CircuitBreaker:
    failure_threshold: int = 5
    recovery_timeout: float = 60.0
    _failure_count: int = field(default=0, init=False)
    _last_failure: float = field(default=0.0, init=False)
    _state: str = field(default="closed", init=False)  # closed | open | half-open

    def record_failure(self) -> None:
        self._failure_count += 1
        self._last_failure = time.time()
        if self._failure_count >= self.failure_threshold:
            self._state = "open"

    def record_success(self) -> None:
        self._failure_count = 0
        self._state = "closed"

    def allow_request(self) -> bool:
        if self._state == "closed":
            return True
        if (
            self._state == "open"
            and time.time() - self._last_failure > self.recovery_timeout
        ):
            self._state = "half-open"
            return True
        return False


def with_retry(max_attempts: int = 3, backoff_factor: float = 0.5):
    """Decorator that retries function on exception."""

    def decorator(func: Callable[P, T]) -> Callable[P, T]:
        @functools.wraps(func)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            last_exc = None
            for attempt in range(max_attempts):
                try:
                    return await func(*args, **kwargs)
                except Exception as exc:  # catch broad, retry on transient failures
                    last_exc = exc
                    if attempt < max_attempts - 1:
                        delay = backoff_factor * (2**attempt)
                        await asyncio.sleep(delay)
            raise last_exc or RuntimeError("Unreachable")

        return wrapper

    return decorator


__all__ = [
    "CircuitBreaker",
    "CircuitBreakerError",
    "with_retry",
]
