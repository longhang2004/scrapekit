"""Synchronous scraper — handles pagination, rate-limiting, retries, and export."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import requests
from loguru import logger

from scrapekit.core.session import build_session, ProxyRotator
from scrapekit.exporters import (
    CSVExporter,
    JSONExporter,
    ExcelExporter,
    SQLiteExporter,
    ParquetExporter,
)
from scrapekit.models.config import AppConfig, ScraperConfig, ExportConfig
from scrapekit.parsers import HTMLParser
from scrapekit.utils import RateLimiter
from scrapekit.utils.retry import retry_on_failure, handle_rate_limit, SoftBanError
from scrapekit.utils.user_agents import random_user_agent


_EXPORTERS = {
    "csv": CSVExporter,
    "json": JSONExporter,
    "excel": ExcelExporter,
    "sqlite": SQLiteExporter,
    "parquet": ParquetExporter,
}


class Scraper:
    """High-level synchronous scraper."""

    def __init__(self, config: AppConfig) -> None:
        self._cfg = config
        self._session = build_session(
            headers=config.scraper.headers,
            max_retries=config.scraper.max_retries,
            rotate_user_agent=config.scraper.rotate_user_agent,
        )
        self._rate_limiter = RateLimiter(
            min_delay=config.scraper.min_delay,
            max_delay=config.scraper.max_delay,
        )
        self._proxy_rotator = ProxyRotator(config.scraper.proxies)
        self._parser = HTMLParser(config.parser)
        self._records: list[dict[str, Any]] = []

        # Optionally set up robots.txt compliance
        self._robots_parser = self._init_robots(config.scraper) if config.scraper.respect_robots_txt else None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run(self, start_url: str | None = None) -> list[dict[str, Any]]:
        url: str | None = start_url or self._cfg.scraper.base_url
        page = 1
        max_pages = self._cfg.scraper.pagination.max_pages

        while url and page <= max_pages:
            logger.info(f"Scraping page {page}: {url}")

            if self._robots_parser and not self._is_allowed(url):
                logger.warning(f"  → Blocked by robots.txt — skipping: {url}")
                break

            html = self._fetch(url)
            if not html:
                break

            records = self._parser.parse(html, base_url=url)
            logger.info(f"  → {len(records)} records found")
            self._records.extend(records)

            if not self._cfg.scraper.pagination.enabled:
                break

            next_url = HTMLParser.find_next_page(
                html,
                self._cfg.scraper.pagination.next_selector,
                base_url=url,
            )
            url = next_url
            page += 1

        if self._cfg.export.dedup_field and self._records:
            self._records = self._deduplicate(self._records, self._cfg.export.dedup_field)

        logger.success(f"Scraping complete — {len(self._records)} total records.")
        return self._records

    def export(self, data: list[dict[str, Any]] | None = None) -> dict[str, Path]:
        records = data or self._records
        if not records:
            raise RuntimeError("No data to export. Run scraper first.")

        output_paths: dict[str, Path] = {}
        prefix = self._cfg.export.filename_prefix

        for fmt in self._cfg.export.formats:
            exporter_cls = _EXPORTERS[fmt]
            exporter = exporter_cls(output_dir=self._cfg.export.output_dir)
            path = exporter.export(records, prefix)
            output_paths[fmt] = path
            logger.info(f"Exported {fmt.upper()}: {path}")

        return output_paths

    def scrape_and_export(self, start_url: str | None = None) -> dict[str, Path]:
        self.run(start_url)
        return self.export()

    def fetch_json(self, url: str, params: dict[str, Any] | None = None) -> Any:
        """Fetch a JSON REST endpoint and return the parsed response."""
        self._rate_limiter.wait()
        proxies = self._proxy_rotator.next_proxy()
        headers = self._rotated_headers()
        resp = self._session.get(
            url,
            params=params,
            timeout=self._cfg.scraper.timeout,
            proxies=proxies,
            headers=headers,
        )
        handle_rate_limit(resp)
        resp.raise_for_status()
        return resp.json()

    @property
    def records(self) -> list[dict[str, Any]]:
        return self._records

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @retry_on_failure(max_attempts=3, min_wait=2, max_wait=30)
    def _fetch(self, url: str) -> str | None:
        self._rate_limiter.wait()
        proxies = self._proxy_rotator.next_proxy()
        headers = self._rotated_headers()
        try:
            resp = self._session.get(
                url,
                timeout=self._cfg.scraper.timeout,
                proxies=proxies,
                headers=headers,
            )
            # Explicit 429 handling with Retry-After
            handle_rate_limit(resp)
            resp.raise_for_status()

            html = resp.text

            # Soft-ban detection
            ban = self._cfg.scraper.ban_indicator
            if ban and ban in html:
                logger.error(f"Soft-ban detected on {url} — response contains '{ban}'")
                raise SoftBanError(f"Soft-ban indicator '{ban}' found in response from {url}")

            # Report proxy success
            if proxies:
                proxy_url = next(iter(proxies.values()))
                self._proxy_rotator.report_success(proxy_url)

            return html

        except requests.RequestException as exc:
            logger.error(f"Failed to fetch {url}: {exc}")
            # Report proxy failure if one was used
            if proxies:
                proxy_url = next(iter(proxies.values()))
                self._proxy_rotator.report_failure(proxy_url)
            return None

    def _rotated_headers(self) -> dict[str, str]:
        """Return per-request headers, rotating User-Agent if configured."""
        if self._cfg.scraper.rotate_user_agent:
            return {"User-Agent": random_user_agent()}
        return {}

    @staticmethod
    def _deduplicate(records: list[dict[str, Any]], field: str) -> list[dict[str, Any]]:
        seen: set[Any] = set()
        unique: list[dict[str, Any]] = []
        for rec in records:
            key = rec.get(field)
            if key not in seen:
                seen.add(key)
                unique.append(rec)
        return unique

    # ------------------------------------------------------------------
    # robots.txt support
    # ------------------------------------------------------------------

    @staticmethod
    def _init_robots(cfg: ScraperConfig):  # type: ignore[return]
        """Load and cache the robots.txt parser for the base URL's domain."""
        try:
            from urllib.robotparser import RobotFileParser
            parsed = urlparse(cfg.base_url)
            robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
            rp = RobotFileParser(robots_url)
            rp.read()
            logger.info(f"Loaded robots.txt from {robots_url}")
            return rp
        except Exception as exc:
            logger.warning(f"Could not load robots.txt: {exc}")
            return None

    def _is_allowed(self, url: str) -> bool:
        if self._robots_parser is None:
            return True
        ua = self._cfg.scraper.headers.get("User-Agent", "*")
        return self._robots_parser.can_fetch(ua, url)
