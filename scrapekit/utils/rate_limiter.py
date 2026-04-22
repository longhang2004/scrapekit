"""Token-bucket rate limiter for polite crawling."""

from __future__ import annotations

import asyncio
import random
import time
from threading import Lock


class RateLimiter:
    """Thread-safe rate limiter with a uniform random delay window.

    Instead of ``delay + jitter`` (which can collapse to near-zero when
    elapsed ≈ delay), we sleep a random value uniformly sampled from
    [min_delay, max_delay] minus any time already elapsed since the last
    request — giving a truly non-uniform, harder-to-fingerprint cadence.
    """

    def __init__(
        self,
        delay: float = 1.0,
        jitter: float = 0.5,
        *,
        min_delay: float | None = None,
        max_delay: float | None = None,
    ) -> None:
        # Accept both old-style (delay/jitter) and new-style (min/max) params.
        self._min = min_delay if min_delay is not None else delay
        self._max = max_delay if max_delay is not None else (delay + jitter)
        if self._min > self._max:
            self._max = self._min
        self._last_call: float = 0.0
        self._lock = Lock()
        self._async_lock: asyncio.Lock | None = None  # created lazily inside event loop

    # ------------------------------------------------------------------
    # Sync path (thread-safe)
    # ------------------------------------------------------------------

    def wait(self) -> None:
        with self._lock:
            elapsed = time.monotonic() - self._last_call
            sleep_for = random.uniform(self._min, self._max) - elapsed
            if sleep_for > 0:
                time.sleep(sleep_for)
            self._last_call = time.monotonic()

    # ------------------------------------------------------------------
    # Async path (coroutine-safe)
    # ------------------------------------------------------------------

    def _get_async_lock(self) -> asyncio.Lock:
        """Lazily create the asyncio.Lock inside an event loop context."""
        if self._async_lock is None:
            self._async_lock = asyncio.Lock()
        return self._async_lock

    async def async_wait(self) -> None:
        async with self._get_async_lock():
            elapsed = time.monotonic() - self._last_call
            sleep_for = random.uniform(self._min, self._max) - elapsed
            if sleep_for > 0:
                await asyncio.sleep(sleep_for)
            self._last_call = time.monotonic()
