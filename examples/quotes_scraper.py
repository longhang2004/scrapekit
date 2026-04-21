"""
Example: Scrape all quotes from quotes.toscrape.com (20 pages).

Run:
    python examples/quotes_scraper.py
"""

from scrapekit import Scraper
from scrapekit.models.config import (
    AppConfig,
    ScraperConfig,
    ParserConfig,
    ExportConfig,
    FieldConfig,
    PaginationConfig,
)

config = AppConfig(
    scraper=ScraperConfig(
        base_url="https://quotes.toscrape.com",
        delay_between_requests=0.8,
        pagination=PaginationConfig(
            enabled=True,
            max_pages=20,
            next_selector="li.next a",
        ),
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
        formats=["csv", "json", "excel"],
        output_dir="./output",
        filename_prefix="quotes",
        dedup_field="text",
    ),
)

if __name__ == "__main__":
    scraper = Scraper(config)
    paths = scraper.scrape_and_export()
    for fmt, path in paths.items():
        print(f"{fmt.upper()}: {path}")
