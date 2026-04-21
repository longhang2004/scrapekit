"""Async scraper using httpx — suitable for high-throughput collection."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import httpx
from loguru import logger

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


_EXPORTERS = {
    "csv": CSVExporter,
    "json": JSONExporter,
    "excel": ExcelExporter,
    "sqlite": SQLiteExporter,
    "parquet": ParquetExporter,
}


class AsyncScraper:
    """Concurrent async scraper — runs multiple requests in parallel."""

    def __init__(self, config: AppConfig) -> None:
        self._cfg = config
        self._rate_limiter = RateLimiter(
            delay=config.scraper.delay_between_requests,
            jitter=config.scraper.delay_jitter,
        )
        self._parser = HTMLParser(config.parser)
        self._semaphore = asyncio.Semaphore(config.scraper.max_concurrent_requests)
        self._records: list[dict[str, Any]] = []

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def run(self, urls: list[str]) -> list[dict[str, Any]]:
        """Scrape a list of URLs concurrently and return all records."""
        async with httpx.AsyncClient(
            headers=self._cfg.scraper.headers,
            timeout=self._cfg.scraper.timeout,
            follow_redirects=True,
        ) as client:
            tasks = [self._scrape_url(client, url) for url in urls]
            results = await asyncio.gather(*tasks, return_exceptions=True)

        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"Error scraping {urls[i]}: {result}")
            else:
                self._records.extend(result)  # type: ignore[arg-type]

        logger.success(f"Async scraping complete — {len(self._records)} records from {len(urls)} URLs.")
        return self._records

    async def run_paginated(self, start_url: str) -> list[dict[str, Any]]:
        """Async paginated scraper (sequential pages, parallel field fetches)."""
        async with httpx.AsyncClient(
            headers=self._cfg.scraper.headers,
            timeout=self._cfg.scraper.timeout,
            follow_redirects=True,
        ) as client:
            url: str | None = start_url
            page = 1
            max_pages = self._cfg.scraper.pagination.max_pages

            while url and page <= max_pages:
                logger.info(f"Page {page}: {url}")
                html = await self._fetch(client, url)
                if not html:
                    break

                records = self._parser.parse(html, base_url=url)
                self._records.extend(records)
                logger.info(f"  → {len(records)} records")

                if not self._cfg.scraper.pagination.enabled:
                    break

                url = HTMLParser.find_next_page(
                    html,
                    self._cfg.scraper.pagination.next_selector,
                    base_url=url,
                )
                page += 1

        return self._records

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

    async def _scrape_url(self, client: httpx.AsyncClient, url: str) -> list[dict[str, Any]]:
        async with self._semaphore:
            await self._rate_limiter.async_wait()
            html = await self._fetch(client, url)
            if not html:
                return []
            return self._parser.parse(html, base_url=url)

    async def _fetch(self, client: httpx.AsyncClient, url: str) -> str | None:
        try:
            resp = await client.get(url)
            resp.raise_for_status()
            return resp.text
        except httpx.HTTPError as exc:
            logger.error(f"HTTP error for {url}: {exc}")
            return None
