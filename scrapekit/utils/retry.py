"""Retry decorator using tenacity with exponential back-off."""

from __future__ import annotations

from functools import wraps
from typing import Any, Callable, TypeVar

from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
    before_sleep_log,
)
from loguru import logger
import requests
import logging

F = TypeVar("F", bound=Callable[..., Any])

_RETRYABLE = (
    requests.exceptions.ConnectionError,
    requests.exceptions.Timeout,
    requests.exceptions.ChunkedEncodingError,
)


def retry_on_failure(max_attempts: int = 3, min_wait: float = 2, max_wait: float = 30) -> Callable[[F], F]:
    """Decorator that retries on transient network errors with exponential back-off."""

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
