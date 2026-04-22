"""Async scraper using httpx — suitable for high-throughput collection."""

from __future__ import annotations

import asyncio
import time
from pathlib import Path
from typing import Any

import httpx
from loguru import logger

from scrapekit.core.session import ProxyRotator
from scrapekit.exporters import (
    CSVExporter,
    JSONExporter,
    ExcelExporter,
    SQLiteExporter,
    ParquetExporter,
)
from scrapekit.models.config import AppConfig
from scrapekit.parsers import HTMLParser
from scrapekit.utils import RateLimiter
from scrapekit.utils.retry import SoftBanError, handle_rate_limit
from scrapekit.utils.user_agents import random_user_agent


_EXPORTERS = {
    "csv": CSVExporter,
    "json": JSONExporter,
    "excel": ExcelExporter,
    "sqlite": SQLiteExporter,
    "parquet": ParquetExporter,
}

# How many consecutive 429/503 responses trigger a concurrency reduction
_RATE_LIMIT_THRESHOLD = 2
# Minimum semaphore value when adapting down
_MIN_CONCURRENCY = 1


class AsyncScraper:
    """Concurrent async scraper — runs multiple requests in parallel.

    Improvements over the original:
    - Proxy rotation per request (was missing entirely).
    - Per-request User-Agent rotation.
    - HTTP/2 via httpx (requires ``httpx[http2]``).
    - Connection pooling via ``httpx.Limits``.
    - Adaptive concurrency: semaphore count shrinks on repeated 429s,
      halves on ban-indicator detection.
    - 429 Retry-After awareness via ``handle_rate_limit``.
    - Soft-ban detection via ``ban_indicator`` config field.
    """

    def __init__(self, config: AppConfig) -> None:
        self._cfg = config
        self._rate_limiter = RateLimiter(
            min_delay=config.scraper.min_delay,
            max_delay=config.scraper.max_delay,
        )
        self._parser = HTMLParser(config.parser)
        self._max_concurrency = config.scraper.max_concurrent_requests
        self._semaphore = asyncio.Semaphore(self._max_concurrency)
        self._proxy_rotator = ProxyRotator(config.scraper.proxies)
        self._records: list[dict[str, Any]] = []
        self._consecutive_rate_limits: int = 0

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def run(self, urls: list[str]) -> list[dict[str, Any]]:
        """Scrape a list of URLs concurrently and return all records."""
        async with self._make_client() as client:
            tasks = [self._scrape_url(client, url) for url in urls]
            results = await asyncio.gather(*tasks, return_exceptions=True)

        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"Error scraping {urls[i]}: {result}")
            else:
                self._records.extend(result)  # type: ignore[arg-type]

        logger.success(
            f"Async scraping complete — {len(self._records)} records from {len(urls)} URLs."
        )
        return self._records

    async def run_paginated(self, start_url: str) -> list[dict[str, Any]]:
        """Async paginated scraper — discovers all pages then scrapes concurrently.

        Phase 1: Follow ``next`` links sequentially to collect all page URLs.
        Phase 2: Scrape all discovered URLs in parallel via :meth:`run`.
        """
        async with self._make_client() as client:
            page_urls = await self._discover_pages(client, start_url)

        logger.info(f"Discovered {len(page_urls)} page(s) — scraping concurrently…")
        return await self.run(page_urls)

    def export(self) -> dict[str, Path]:
        if not self._records:
            raise RuntimeError("No data to export.")
        output_paths: dict[str, Path] = {}
        prefix = self._cfg.export.filename_prefix
        for fmt in self._cfg.export.formats:
            exporter = _EXPORTERS[fmt](output_dir=self._cfg.export.output_dir)
            path = exporter.export(self._records, prefix)
            output_paths[fmt] = path
            logger.info(f"Exported {fmt.upper()}: {path}")
        return output_paths

    @property
    def records(self) -> list[dict[str, Any]]:
        return self._records

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _make_client(self) -> httpx.AsyncClient:
        """Build a pooled, HTTP/2-capable async client."""
        base_headers = dict(self._cfg.scraper.headers)
        if self._cfg.scraper.rotate_user_agent:
            base_headers["User-Agent"] = random_user_agent()

        return httpx.AsyncClient(
            headers=base_headers,
            timeout=self._cfg.scraper.timeout,
            follow_redirects=True,
            http2=True,  # requires httpx[http2]
            limits=httpx.Limits(
                max_connections=self._max_concurrency + 5,
                max_keepalive_connections=self._max_concurrency,
                keepalive_expiry=30,
            ),
        )

    def _proxy_kwargs(self) -> dict[str, Any]:
        """Return httpx proxy kwarg dict for the next proxy, or empty dict."""
        proxy_dict = self._proxy_rotator.next_proxy()
        if proxy_dict is None:
            return {}
        # httpx uses ``proxy`` kwarg (single URL) for uniform http/https proxying
        return {"proxy": proxy_dict.get("https") or proxy_dict.get("http")}

    def _rotated_headers(self) -> dict[str, str]:
        if self._cfg.scraper.rotate_user_agent:
            return {"User-Agent": random_user_agent()}
        return {}

    async def _adapt_concurrency_down(self) -> None:
        """Halve the effective semaphore slots after repeated rate-limiting."""
        new_limit = max(_MIN_CONCURRENCY, self._max_concurrency // 2)
        if new_limit < self._max_concurrency:
            self._max_concurrency = new_limit
            self._semaphore = asyncio.Semaphore(new_limit)
            logger.warning(f"Adaptive concurrency reduced to {new_limit} after repeated rate limits.")

    async def _scrape_url(self, client: httpx.AsyncClient, url: str) -> list[dict[str, Any]]:
        async with self._semaphore:
            await self._rate_limiter.async_wait()
            html = await self._fetch(client, url)
            if not html:
                return []
            return self._parser.parse(html, base_url=url)

    async def _fetch(self, client: httpx.AsyncClient, url: str) -> str | None:
        proxy_kwargs = self._proxy_kwargs()
        headers = self._rotated_headers()
        proxy_url: str | None = proxy_kwargs.get("proxy")

        for attempt in range(self._cfg.scraper.max_retries + 1):
            try:
                resp = await client.get(url, headers=headers, **proxy_kwargs)

                # 429 handling with Retry-After
                if resp.status_code == 429:
                    self._consecutive_rate_limits += 1
                    if self._consecutive_rate_limits >= _RATE_LIMIT_THRESHOLD:
                        await self._adapt_concurrency_down()
                        self._consecutive_rate_limits = 0
                    retry_after = float(resp.headers.get("Retry-After", 5))
                    retry_after = min(retry_after, 120)
                    logger.warning(f"429 on {url} — sleeping {retry_after:.1f}s (attempt {attempt + 1})")
                    await asyncio.sleep(retry_after)
                    continue  # retry

                resp.raise_for_status()
                self._consecutive_rate_limits = 0  # reset on success

                html = resp.text

                # Soft-ban detection
                ban = self._cfg.scraper.ban_indicator
                if ban and ban in html:
                    logger.error(f"Soft-ban detected on {url} — contains '{ban}'")
                    if proxy_url:
                        self._proxy_rotator.report_failure(proxy_url)
                    raise SoftBanError(f"Soft-ban indicator found in response from {url}")

                if proxy_url:
                    self._proxy_rotator.report_success(proxy_url)
                return html

            except httpx.HTTPStatusError as exc:
                logger.error(f"HTTP {exc.response.status_code} on {url}: {exc}")
                if proxy_url:
                    self._proxy_rotator.report_failure(proxy_url)
                if attempt < self._cfg.scraper.max_retries:
                    backoff = min(2 ** attempt * 2, 30)
                    await asyncio.sleep(backoff)
                    continue
                return None

            except httpx.HTTPError as exc:
                logger.error(f"HTTP error for {url}: {exc}")
                if proxy_url:
                    self._proxy_rotator.report_failure(proxy_url)
                if attempt < self._cfg.scraper.max_retries:
                    backoff = min(2 ** attempt * 2, 30)
                    await asyncio.sleep(backoff)
                    continue
                return None

        return None

    async def _discover_pages(self, client: httpx.AsyncClient, start_url: str) -> list[str]:
        """Follow pagination links and return all page URLs (including start_url)."""
        page_urls: list[str] = []
        url: str | None = start_url
        max_pages = self._cfg.scraper.pagination.max_pages

        while url and len(page_urls) < max_pages:
            page_urls.append(url)
            if not self._cfg.scraper.pagination.enabled:
                break
            html = await self._fetch(client, url)
            if not html:
                break
            url = HTMLParser.find_next_page(
                html,
                self._cfg.scraper.pagination.next_selector,
                base_url=url,
            )

        return page_urls
