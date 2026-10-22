"""A token-bucket rate limiter that works from any thread or event loop.

State is guarded by a thread lock and waiting is a plain ``sleep`` on whichever loop
is running, so one bucket can be shared by the sync facade and an async server.
"""

import asyncio
import threading
import time
from collections.abc import Awaitable, Callable

from xippios.core.client.config import RateLimit

__all__ = ["TokenBucket"]


class TokenBucket:
    """Token bucket for a ``RateLimit``.

    Args:
        limit: Sustained rate and burst size.
        clock: Monotonic time source in seconds, replaceable in tests.
    """

    def __init__(self, limit: RateLimit, *, clock: Callable[[], float] = time.monotonic) -> None:
        self.limit = limit
        self._rate = limit.per_second
        self._capacity = float(limit.capacity)
        self._tokens = self._capacity
        self._clock = clock
        self._updated = clock()
        self._lock = threading.Lock()

    def reserve(self) -> float:
        """Take one token and return the seconds to wait before using it.

        Reservations may drive the balance negative, which queues callers in order:
        each one gets the next free slot.
        """
        with self._lock:
            now = self._clock()
            elapsed = max(0.0, now - self._updated)
            self._tokens = min(self._capacity, self._tokens + elapsed * self._rate)
            self._updated = now
            self._tokens -= 1.0
            if self._tokens >= 0:
                return 0.0
            return -self._tokens / self._rate

    async def acquire(self, sleep: Callable[[float], Awaitable[None]] = asyncio.sleep) -> float:
        """Reserve a slot and wait for it; returns the seconds waited."""
        wait = self.reserve()
        if wait > 0:
            await sleep(wait)
        return wait
