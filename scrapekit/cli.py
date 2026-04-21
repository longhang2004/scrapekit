"""Command-line interface for ScrapeKit."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import click
from rich.console import Console
from rich.table import Table

from scrapekit.core.scraper import Scraper
from scrapekit.models.config import AppConfig, ScraperConfig, ParserConfig, ExportConfig, AppConfig


console = Console()


@click.group()
@click.version_option("1.0.0", prog_name="scrapekit")
def main() -> None:
    """ScrapeKit — professional web data extraction toolkit."""


@main.command("run")
@click.option("--config", "-c", required=True, type=click.Path(exists=True), help="Path to YAML config file.")
@click.option("--url", "-u", default=None, help="Override the base URL in config.")
@click.option("--formats", "-f", default=None, help="Comma-separated export formats (csv,json,excel,sqlite,parquet).")
@click.option("--output", "-o", default=None, type=click.Path(), help="Override output directory.")
def run_command(config: str, url: Optional[str], formats: Optional[str], output: Optional[str]) -> None:
    """Run a scraping job defined by a YAML config file."""
    app_cfg = AppConfig.from_yaml(config)

    if url:
        app_cfg.scraper.base_url = url
    if formats:
        app_cfg.export.formats = [f.strip() for f in formats.split(",")]  # type: ignore[assignment]
    if output:
        app_cfg.export.output_dir = Path(output)
        app_cfg.export.output_dir.mkdir(parents=True, exist_ok=True)

    scraper = Scraper(app_cfg)

    with console.status("[bold green]Scraping…"):
        paths = scraper.scrape_and_export()

    _print_summary(scraper.records, paths)


@main.command("fetch")
@click.argument("url")
@click.option("--selector", "-s", default="body", show_default=True, help="CSS selector for items.")
@click.option("--field", "-F", multiple=True, help="field:selector[:attribute] — repeatable.")
@click.option("--formats", "-f", default="csv,json", show_default=True, help="Comma-separated export formats.")
@click.option("--output", "-o", default="./output", show_default=True, type=click.Path(), help="Output directory.")
@click.option("--pages", "-p", default=1, show_default=True, help="Max pages to crawl.")
@click.option("--next", "next_selector", default="li.next a", show_default=True, help="CSS selector for next-page link.")
@click.option("--delay", "-d", default=1.0, show_default=True, help="Delay between requests (seconds).")
def fetch_command(
    url: str,
    selector: str,
    field: tuple[str, ...],
    formats: str,
    output: str,
    pages: int,
    next_selector: str,
    delay: float,
) -> None:
    """Quick one-shot scrape without a config file.

    Example:

        scrapekit fetch https://books.toscrape.com \\
            --selector "article.product_pod" \\
            --field "title:h3 a:title" \\
            --field "price:p.price_color" \\
            --formats csv,json --pages 5
    """
    from scrapekit.models.config import (
        FieldConfig,
        PaginationConfig,
        LoggingConfig,
    )

    fields: dict = {}
    for f in field:
        parts = f.split(":", 2)
        if len(parts) < 2:
            raise click.BadParameter(f"Invalid field spec: '{f}'. Use field:selector[:attribute]")
        name, css = parts[0], parts[1]
        attr = parts[2] if len(parts) == 3 else None
        fields[name] = FieldConfig(selector=css, attribute=attr)

    app_cfg = AppConfig(
        scraper=ScraperConfig(
            base_url=url,
            delay_between_requests=delay,
            pagination=PaginationConfig(
                enabled=pages > 1,
                max_pages=pages,
                next_selector=next_selector,
            ),
        ),
        parser=ParserConfig(item_selector=selector, fields=fields),
        export=ExportConfig(
            formats=[f.strip() for f in formats.split(",")],  # type: ignore[assignment]
            output_dir=Path(output),
        ),
    )

    scraper = Scraper(app_cfg)
    with console.status("[bold green]Scraping…"):
        paths = scraper.scrape_and_export()

    _print_summary(scraper.records, paths)


@main.command("preview")
@click.argument("url")
@click.option("--selector", "-s", default="body", help="CSS selector for items.")
@click.option("--field", "-F", multiple=True, help="field:selector[:attribute] — repeatable.")
@click.option("--limit", "-l", default=5, show_default=True, help="Max rows to preview.")
def preview_command(url: str, selector: str, field: tuple[str, ...], limit: int) -> None:
    """Preview scraped data in the terminal without exporting.

    Example:

        scrapekit preview https://quotes.toscrape.com \\
            --selector "div.quote" \\
            --field "text:span.text" \\
            --field "author:small.author"
    """
    from scrapekit.models.config import FieldConfig, LoggingConfig

    fields: dict = {}
    for f in field:
        parts = f.split(":", 2)
        if len(parts) < 2:
            raise click.BadParameter(f"Invalid field spec: '{f}'")
        name, css = parts[0], parts[1]
        attr = parts[2] if len(parts) == 3 else None
        fields[name] = FieldConfig(selector=css, attribute=attr)

    import requests
    resp = requests.get(url, timeout=30, headers={"User-Agent": "ScrapeKit/1.0"})
    resp.raise_for_status()

    from scrapekit.parsers import HTMLParser
    from scrapekit.models.config import ParserConfig

    parser = HTMLParser(ParserConfig(item_selector=selector, fields=fields))
    records = parser.parse(resp.text, base_url=url)[:limit]

    if not records:
        console.print("[yellow]No records found with those selectors.[/yellow]")
        return

    table = Table(title=f"Preview — {url}", show_lines=True)
    for col in records[0]:
        table.add_column(col, overflow="fold")
    for row in records:
        table.add_row(*[str(v) if v is not None else "" for v in row.values()])
    console.print(table)


def _print_summary(records: list, paths: dict) -> None:
    console.print(f"\n[bold green]Done![/bold green] {len(records)} records scraped.\n")
    table = Table(title="Export Summary", show_header=True, header_style="bold blue")
    table.add_column("Format", style="cyan")
    table.add_column("Path", style="white")
    for fmt, path in paths.items():
        table.add_row(fmt.upper(), str(path))
    console.print(table)
