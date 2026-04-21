"""Token-bucket rate limiter for polite crawling."""

from __future__ import annotations

import asyncio
import random
import time
from threading import Lock


class RateLimiter:
    """Thread-safe rate limiter with optional jitter."""

    def __init__(self, delay: float = 1.0, jitter: float = 0.3) -> None:
        self._delay = delay
        self._jitter = jitter
        self._last_call: float = 0.0
        self._lock = Lock()

    def wait(self) -> None:
        with self._lock:
            elapsed = time.monotonic() - self._last_call
            sleep_for = self._delay + random.uniform(0, self._jitter) - elapsed
            if sleep_for > 0:
                time.sleep(sleep_for)
            self._last_call = time.monotonic()

    async def async_wait(self) -> None:
        elapsed = time.monotonic() - self._last_call
        sleep_for = self._delay + random.uniform(0, self._jitter) - elapsed
        if sleep_for > 0:
            await asyncio.sleep(sleep_for)
        self._last_call = time.monotonic()
