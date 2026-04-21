"""
Example: Async concurrent scraping of multiple URLs.

Run:
    python examples/async_scraper_example.py
"""

from __future__ import annotations

import asyncio

from scrapekit import AsyncScraper
from scrapekit.models.config import (
    AppConfig,
    ScraperConfig,
    ParserConfig,
    ExportConfig,
    FieldConfig,
)

URLS = [
    f"https://quotes.toscrape.com/page/{i}/"
    for i in range(1, 6)
]

config = AppConfig(
    scraper=ScraperConfig(
        base_url="https://quotes.toscrape.com",
        delay_between_requests=0.5,
        max_concurrent_requests=3,
    ),
    parser=ParserConfig(
        item_selector="div.quote",
        fields={
            "text": FieldConfig(selector="span.text"),
            "author": FieldConfig(selector="small.author"),
            "tags": FieldConfig(selector="div.tags"),
        },
    ),
    export=ExportConfig(
        formats=["csv", "json"],
        output_dir="./output",
        filename_prefix="async_quotes",
    ),
)


async def main() -> None:
    scraper = AsyncScraper(config)
    await scraper.run(URLS)
    paths = scraper.export()
    for fmt, path in paths.items():
        print(f"{fmt.upper()}: {path}")


if __name__ == "__main__":
    asyncio.run(main())
