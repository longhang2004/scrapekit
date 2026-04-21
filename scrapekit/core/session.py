"""Shared session factory with proxy rotation and header management."""

from __future__ import annotations

import itertools
from typing import Iterator

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


def build_session(
    headers: dict[str, str],
    max_retries: int = 3,
) -> requests.Session:
    session = requests.Session()
    session.headers.update(headers)

    retry_strategy = Retry(
        total=max_retries,
        backoff_factor=1,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET", "POST"],
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


class ProxyRotator:
    """Round-robin proxy rotator."""

    def __init__(self, proxies: list[str]) -> None:
        self._cycle: Iterator[str] | None = itertools.cycle(proxies) if proxies else None

    def next_proxy(self) -> dict[str, str] | None:
        if self._cycle is None:
            return None
        proxy = next(self._cycle)
        return {"http": proxy, "https": proxy}
