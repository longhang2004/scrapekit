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
                value: str | None = el.get(field_cfg.attribute)  # type: ignore[assignment]
                # Resolve relative URLs
                if field_cfg.attribute in ("href", "src") and value and base_url:
                    if value.startswith("/"):
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
        href: str | None = el.get("href")  # type: ignore[assignment]
        if href and base_url and href.startswith("/"):
            from urllib.parse import urljoin
            return urljoin(base_url, href)
        return href
