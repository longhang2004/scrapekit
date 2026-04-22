"""Shared session factory with proxy rotation and header management."""

from __future__ import annotations

import itertools
from collections import defaultdict
from typing import Iterator

import requests
from loguru import logger
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from scrapekit.utils.user_agents import random_user_agent


def build_session(
    headers: dict[str, str],
    max_retries: int = 3,
    rotate_user_agent: bool = True,
) -> requests.Session:
    """Build a requests.Session with retry strategy and browser-like headers.

    Args:
        headers: Base headers merged into every request.
        max_retries: Number of urllib3-level retries on transient errors.
        rotate_user_agent: If True the User-Agent in ``headers`` is ignored
            and a random one is picked per session construction. The scraper
            layer further rotates per-request when this flag is set.
    """
    session = requests.Session()

    # Apply a random UA unless the caller explicitly set one and rotation is off
    effective_headers = dict(headers)
    if rotate_user_agent or "User-Agent" not in effective_headers:
        effective_headers["User-Agent"] = random_user_agent()

    session.headers.update(effective_headers)

    retry_strategy = Retry(
        total=max_retries,
        backoff_factor=1,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET", "POST"],
        raise_on_status=False,
        # Respect Retry-After header sent by the server on 429/503
        respect_retry_after_header=True,
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


class ProxyRotator:
    """Round-robin proxy rotator with dead-proxy blacklisting.

    A proxy is blacklisted after ``max_failures`` consecutive failures and
    is removed from rotation permanently (with a log warning). If all proxies
    are blacklisted the rotator falls back to a direct (no-proxy) connection.
    """

    def __init__(self, proxies: list[str], max_failures: int = 3) -> None:
        self._proxies: list[str] = list(proxies)
        self._max_failures = max_failures
        self._failures: dict[str, int] = defaultdict(int)
        self._blacklist: set[str] = set()
        self._cycle: Iterator[str] | None = self._make_cycle()

    # ------------------------------------------------------------------

    def next_proxy(self) -> dict[str, str] | None:
        """Return the next healthy proxy dict, or None for a direct connection."""
        if self._cycle is None:
            return None
        for _ in range(len(self._proxies) + 1):
            try:
                proxy = next(self._cycle)
            except StopIteration:
                return None
            if proxy not in self._blacklist:
                return {"http": proxy, "https": proxy}
        # All proxies exhausted / blacklisted — go direct
        return None

    def report_failure(self, proxy_url: str) -> None:
        """Increment failure count for a proxy; blacklist after max_failures."""
        self._failures[proxy_url] += 1
        if self._failures[proxy_url] >= self._max_failures:
            self._blacklist.add(proxy_url)
            logger.warning(
                f"Proxy blacklisted after {self._max_failures} consecutive failures: {proxy_url}"
            )
            # Rebuild cycle without blacklisted proxies
            self._cycle = self._make_cycle()

    def report_success(self, proxy_url: str) -> None:
        """Reset failure counter on success."""
        self._failures[proxy_url] = 0

    # ------------------------------------------------------------------

    def _make_cycle(self) -> Iterator[str] | None:
        live = [p for p in self._proxies if p not in self._blacklist]
        return itertools.cycle(live) if live else None
