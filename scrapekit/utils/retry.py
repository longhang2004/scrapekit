"""Retry decorator using tenacity with exponential back-off and 429 awareness."""

from __future__ import annotations

import logging
import time
from functools import wraps
from typing import Any, Callable, TypeVar

import httpx
import requests
from loguru import logger
from tenacity import (
    before_sleep_log,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

F = TypeVar("F", bound=Callable[..., Any])

# Transient errors from both the sync (requests) and async (httpx) clients
_RETRYABLE = (
    requests.exceptions.ConnectionError,
    requests.exceptions.Timeout,
    requests.exceptions.ChunkedEncodingError,
    httpx.ConnectError,
    httpx.TimeoutException,
    httpx.RemoteProtocolError,
    httpx.ReadError,
)


class SoftBanError(RuntimeError):
    """Raised when a response body contains a known ban-indicator string."""


class RateLimitedError(requests.exceptions.HTTPError):
    """Raised when a 429 response is encountered (wraps the original response)."""


def retry_on_failure(
    max_attempts: int = 3,
    min_wait: float = 2,
    max_wait: float = 30,
) -> Callable[[F], F]:
    """Decorator that retries on transient network errors with exponential back-off.

    Retries on:
    - Network-level errors (connection reset, timeout, chunked-encoding)
    - Both ``requests`` and ``httpx`` exception types
    """

    def decorator(func: F) -> F:
        @retry(
            reraise=True,
            stop=stop_after_attempt(max_attempts),
            wait=wait_exponential(multiplier=1, min=min_wait, max=max_wait),
            retry=retry_if_exception_type(_RETRYABLE),
            before_sleep=before_sleep_log(logging.getLogger("scrapekit"), logging.WARNING),
        )
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            return func(*args, **kwargs)

        return wrapper  # type: ignore[return-value]

    return decorator


def handle_rate_limit(response: requests.Response | httpx.Response, max_wait: float = 120) -> None:
    """If *response* is a 429, sleep for ``Retry-After`` seconds then raise.

    Call this immediately after receiving a response, before raising for status.
    """
    if response.status_code != 429:
        return
    retry_after_raw = response.headers.get("Retry-After", "")
    try:
        wait = min(float(retry_after_raw), max_wait)
    except (ValueError, TypeError):
        wait = 5.0  # sensible default when header is absent or non-numeric
    logger.warning(f"Rate limited (429). Sleeping {wait:.1f}s before retry…")
    time.sleep(wait)
    raise RateLimitedError(f"HTTP 429 — rate limited, waited {wait:.1f}s", response=response)  # type: ignore[call-arg]
