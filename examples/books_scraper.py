"""
Example: Scrape books from books.toscrape.com with all export formats.

Run:
    python examples/books_scraper.py
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
        base_url="https://books.toscrape.com/catalogue/page-1.html",
        delay_between_requests=1.0,
        delay_jitter=0.3,
        pagination=PaginationConfig(
            enabled=True,
            max_pages=50,
            next_selector="li.next a",
        ),
    ),
    parser=ParserConfig(
        item_selector="article.product_pod",
        fields={
            "title": FieldConfig(selector="h3 a", attribute="title"),
            "price": FieldConfig(selector="p.price_color"),
            "rating": FieldConfig(selector="p.star-rating", attribute="class"),
            "availability": FieldConfig(selector="p.availability"),
            "url": FieldConfig(selector="h3 a", attribute="href"),
        },
    ),
    export=ExportConfig(
        formats=["csv", "json", "excel", "sqlite", "parquet"],
        output_dir="./output",
        filename_prefix="books",
        dedup_field="title",
    ),
)

if __name__ == "__main__":
    scraper = Scraper(config)
    paths = scraper.scrape_and_export()
    for fmt, path in paths.items():
        print(f"{fmt.upper()}: {path}")
