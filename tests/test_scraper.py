"""Tests for the synchronous Scraper with mocked HTTP responses."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import responses as resp_mock

from scrapekit.core.scraper import Scraper
from scrapekit.models.config import (
    AppConfig,
    ScraperConfig,
    ParserConfig,
    ExportConfig,
    FieldConfig,
    PaginationConfig,
)


PAGE_1 = """
<html><body>
  <ul>
    <li class="item"><span class="name">Item 1</span><span class="price">10</span></li>
    <li class="item"><span class="name">Item 2</span><span class="price">20</span></li>
  </ul>
  <li class="next"><a href="http://example.com/page/2">Next</a></li>
</body></html>
"""

PAGE_2 = """
<html><body>
  <ul>
    <li class="item"><span class="name">Item 3</span><span class="price">30</span></li>
  </ul>
</body></html>
"""


def make_config(tmp_path: Path, paginate: bool = False) -> AppConfig:
    return AppConfig(
        scraper=ScraperConfig(
            base_url="http://example.com/page/1",
            delay_between_requests=0,
            delay_jitter=0,
            pagination=PaginationConfig(
                enabled=paginate,
                max_pages=2,
                next_selector="li.next a",
            ),
        ),
        parser=ParserConfig(
            item_selector="li.item",
            fields={
                "name": FieldConfig(selector="span.name"),
                "price": FieldConfig(selector="span.price"),
            },
        ),
        export=ExportConfig(
            formats=["csv", "json"],
            output_dir=tmp_path,
            filename_prefix="test_output",
        ),
    )


@resp_mock.activate
def test_single_page_scrape(tmp_path: Path) -> None:
    resp_mock.add(resp_mock.GET, "http://example.com/page/1", body=PAGE_1, status=200)
    scraper = Scraper(make_config(tmp_path))
    records = scraper.run()
    assert len(records) == 2
    assert records[0]["name"] == "Item 1"


@resp_mock.activate
def test_paginated_scrape(tmp_path: Path) -> None:
    resp_mock.add(resp_mock.GET, "http://example.com/page/1", body=PAGE_1, status=200)
    resp_mock.add(resp_mock.GET, "http://example.com/page/2", body=PAGE_2, status=200)
    scraper = Scraper(make_config(tmp_path, paginate=True))
    records = scraper.run()
    assert len(records) == 3
    assert records[2]["name"] == "Item 3"


@resp_mock.activate
def test_export_creates_files(tmp_path: Path) -> None:
    resp_mock.add(resp_mock.GET, "http://example.com/page/1", body=PAGE_1, status=200)
    scraper = Scraper(make_config(tmp_path))
    paths = scraper.scrape_and_export()
    assert paths["csv"].exists()
    assert paths["json"].exists()


@resp_mock.activate
def test_failed_fetch_returns_empty(tmp_path: Path) -> None:
    resp_mock.add(resp_mock.GET, "http://example.com/page/1", status=500)
    scraper = Scraper(make_config(tmp_path))
    records = scraper.run()
    assert records == []


def test_export_without_run_raises(tmp_path: Path) -> None:
    scraper = Scraper(make_config(tmp_path))
    with pytest.raises(RuntimeError):
        scraper.export()


def test_deduplication() -> None:
    records = [
        {"name": "A", "price": 1},
        {"name": "A", "price": 2},
        {"name": "B", "price": 3},
    ]
    result = Scraper._deduplicate(records, "name")
    assert len(result) == 2
    assert result[0]["price"] == 1
