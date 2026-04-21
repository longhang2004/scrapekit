# ScrapeKit

A professional, production-ready web data extraction toolkit built in Python. Scrape any website or REST API and export the results to **CSV, JSON, Excel, SQLite, or Parquet** — all from a single config file or a one-line CLI command.

---

## Features

| Feature | Details |
|---|---|
| **Multi-format export** | CSV · JSON · Excel (styled) · SQLite · Parquet |
| **Sync & Async scrapers** | `requests` for simple jobs, `httpx` + `asyncio` for high-throughput |
| **Config-driven** | Describe your scrape in a YAML file — no code required |
| **CLI interface** | `scrapekit run`, `scrapekit fetch`, `scrapekit preview` |
| **Pagination** | Automatic next-page following via CSS selector |
| **Rate limiting** | Polite delays with optional jitter to avoid detection |
| **Retry logic** | Exponential back-off on network/server errors |
| **Proxy rotation** | Round-robin over a list of HTTP/HTTPS proxies |
| **Table extraction** | Pull `<table>` elements straight into DataFrames |
| **Data deduplication** | Deduplicate records by any field before export |
| **Type-safe config** | Pydantic v2 models validate every config option |

---

## Quick Start

### Installation

```bash
# Clone the repo
git clone https://github.com/longhang/scrapekit.git
cd scrapekit

# Create a virtual environment and install
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
```

### 1 — Run with a config file

```bash
# Copy the example config and edit it
cp config/example_config.yaml my_job.yaml

# Run
scrapekit run --config my_job.yaml
```

### 2 — Quick scrape from the command line (no config file)

```bash
scrapekit fetch https://quotes.toscrape.com \
  --selector "div.quote" \
  --field "text:span.text" \
  --field "author:small.author" \
  --formats csv,json,excel \
  --pages 5
```

### 3 — Preview data in the terminal before exporting

```bash
scrapekit preview https://books.toscrape.com \
  --selector "article.product_pod" \
  --field "title:h3 a:title" \
  --field "price:p.price_color" \
  --limit 10
```

---

## Python API

### Sync scraper

```python
from scrapekit import Scraper
from scrapekit.models.config import (
    AppConfig, ScraperConfig, ParserConfig, ExportConfig,
    FieldConfig, PaginationConfig,
)

config = AppConfig(
    scraper=ScraperConfig(
        base_url="https://books.toscrape.com/catalogue/page-1.html",
        delay_between_requests=1.0,
        pagination=PaginationConfig(enabled=True, max_pages=50),
    ),
    parser=ParserConfig(
        item_selector="article.product_pod",
        fields={
            "title": FieldConfig(selector="h3 a", attribute="title"),
            "price": FieldConfig(selector="p.price_color"),
        },
    ),
    export=ExportConfig(
        formats=["csv", "json", "excel", "sqlite"],
        output_dir="./output",
        filename_prefix="books",
    ),
)

scraper = Scraper(config)
paths = scraper.scrape_and_export()
# → output/books.csv, output/books.json, output/books.xlsx, output/books.db
```

### Async scraper (concurrent)

```python
import asyncio
from scrapekit import AsyncScraper

async def main():
    scraper = AsyncScraper(config)  # same AppConfig object
    await scraper.run([
        "https://example.com/page/1",
        "https://example.com/page/2",
    ])
    scraper.export()

asyncio.run(main())
```

### Table extraction

```python
import requests
from scrapekit.parsers import TableParser
from scrapekit.exporters import CSVExporter

html = requests.get("https://en.wikipedia.org/wiki/List_of_countries_by_GDP_(nominal)").text
df = TableParser().parse_by_index(html, index=0)
CSVExporter("./output").export_dataframe(df, "gdp")
```

### Use exporters standalone

```python
from scrapekit.exporters import ExcelExporter, ParquetExporter

data = [{"product": "Widget", "price": 9.99}, ...]

ExcelExporter("./output").export(data, "products")
ParquetExporter("./output").export(data, "products")
```

---

## Config Reference

```yaml
scraper:
  base_url: "https://example.com"
  timeout: 30
  max_retries: 3
  delay_between_requests: 1.0
  delay_jitter: 0.3
  max_concurrent_requests: 5
  proxies:
    - "http://user:pass@proxy.example.com:8080"
  headers:
    User-Agent: "Mozilla/5.0 ..."
  pagination:
    enabled: true
    max_pages: 50
    next_selector: "li.next a"

parser:
  item_selector: "article.product_pod"
  fields:
    title:
      selector: "h3 a"
      attribute: "title"   # omit for inner text
    price:
      selector: "p.price_color"

export:
  formats: [csv, json, excel, sqlite, parquet]
  output_dir: "./output"
  filename_prefix: "my_data"
  dedup_field: "title"

logging:
  level: "INFO"
  file: "logs/scrapekit.log"
  rotation: "10 MB"
```

---

## Project Structure

```
scrapekit/
├── scrapekit/
│   ├── core/
│   │   ├── scraper.py          # Synchronous scraper
│   │   ├── async_scraper.py    # Async / concurrent scraper
│   │   └── session.py          # Session factory + proxy rotator
│   ├── exporters/
│   │   ├── base.py             # Abstract base exporter
│   │   ├── csv_exporter.py
│   │   ├── json_exporter.py
│   │   ├── excel_exporter.py   # Styled Excel output
│   │   ├── sqlite_exporter.py
│   │   └── parquet_exporter.py
│   ├── parsers/
│   │   ├── html_parser.py      # CSS-selector parser
│   │   └── table_parser.py     # HTML table → DataFrame
│   ├── models/
│   │   └── config.py           # Pydantic config models
│   ├── utils/
│   │   ├── logger.py
│   │   ├── rate_limiter.py
│   │   └── retry.py
│   └── cli.py                  # Click-based CLI
├── examples/
│   ├── quotes_scraper.py
│   ├── books_scraper.py
│   ├── api_scraper.py
│   ├── async_scraper_example.py
│   └── table_scraper_example.py
├── tests/
│   ├── test_exporters.py
│   ├── test_parsers.py
│   └── test_scraper.py
├── config/
│   └── example_config.yaml
└── pyproject.toml
```

---

## Running Tests

```bash
pytest
# with coverage report
pytest --cov=scrapekit --cov-report=html
```

---

## Examples

| Script | What it does |
|---|---|
| `examples/books_scraper.py` | Scrapes all 1,000 books from books.toscrape.com → 5 formats |
| `examples/quotes_scraper.py` | Scrapes 100 quotes across 10 pages |
| `examples/api_scraper.py` | Fetches JSONPlaceholder REST API → CSV + JSON + Excel |
| `examples/async_scraper_example.py` | Concurrent async scrape of 5 pages |
| `examples/table_scraper_example.py` | Extracts Wikipedia HTML table → CSV + Excel |

---

## Tech Stack

- **HTTP** — `requests`, `httpx`, `aiohttp`
- **Parsing** — `beautifulsoup4`, `lxml`
- **Data** — `pandas`, `pyarrow`
- **Export** — `openpyxl`, `sqlite3`
- **Config** — `pydantic v2`, `pyyaml`
- **CLI** — `click`, `rich`
- **Reliability** — `tenacity`, `loguru`
- **Tests** — `pytest`, `responses`

---

## License

MIT © Long Hang
