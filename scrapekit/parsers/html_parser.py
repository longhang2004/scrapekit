"""CSS-selector driven HTML parser backed by BeautifulSoup."""

from __future__ import annotations

from typing import Any

from bs4 import BeautifulSoup, Tag

from scrapekit.models.config import ParserConfig


class HTMLParser:
    """Extract structured records from an HTML page using CSS selectors."""

    def __init__(self, config: ParserConfig) -> None:
        self._config = config

    def parse(self, html: str, base_url: str = "") -> list[dict[str, Any]]:
        soup = BeautifulSoup(html, "lxml")
        items = soup.select(self._config.item_selector)
        records: list[dict[str, Any]] = []
        for item in items:
            record = self._extract_fields(item, base_url)
            if record:
                records.append(record)
        return records

    def _extract_fields(self, item: Tag, base_url: str) -> dict[str, Any]:
        record: dict[str, Any] = {}
        for field_name, field_cfg in self._config.fields.items():
            el = item.select_one(field_cfg.selector)
            if el is None:
                record[field_name] = None
                continue
            if field_cfg.attribute:
                raw = el.get(field_cfg.attribute)
                # BS4 returns list for multi-valued attrs (e.g. class); normalise to str
                value: str | None = " ".join(raw) if isinstance(raw, list) else raw
                # Resolve relative URLs
                if field_cfg.attribute in ("href", "src") and value and base_url:
                    if not value.startswith(("http://", "https://")):
                        from urllib.parse import urljoin
                        value = urljoin(base_url, value)
            else:
                value = el.get_text(strip=True)
            record[field_name] = value
        return record

    @staticmethod
    def find_next_page(html: str, selector: str, base_url: str = "") -> str | None:
        soup = BeautifulSoup(html, "lxml")
        el = soup.select_one(selector)
        if el is None:
            return None
        raw_href = el.get("href")
        href: str | None = " ".join(raw_href) if isinstance(raw_href, list) else raw_href
        if href and base_url and not href.startswith(("http://", "https://")):
            from urllib.parse import urljoin
            return urljoin(base_url, href)
        return href
