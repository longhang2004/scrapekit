"""
Example: Extract HTML tables from Wikipedia and export as CSV + Excel.

Run:
    python examples/table_scraper_example.py
"""

from __future__ import annotations

import requests

from scrapekit.parsers import TableParser
from scrapekit.exporters import CSVExporter, ExcelExporter

URL = "https://en.wikipedia.org/wiki/List_of_countries_by_GDP_(nominal)"


def main() -> None:
    print(f"Fetching {URL} …")
    resp = requests.get(URL, timeout=30, headers={"User-Agent": "ScrapeKit/1.0"})
    resp.raise_for_status()

    parser = TableParser()
    tables = parser.parse_all(resp.text)
    print(f"  {len(tables)} table(s) found on page.")

    # The first table is typically the main GDP table
    df = tables[0]
    print(f"  Columns: {list(df.columns)}")
    print(f"  Rows: {len(df)}")

    output_dir = "./output"
    filename = "gdp_by_country"

    csv_path  = CSVExporter(output_dir).export_dataframe(df, filename)
    xlsx_path = ExcelExporter(output_dir).export_dataframe(df, filename)

    print(f"CSV   : {csv_path}")
    print(f"Excel : {xlsx_path}")


if __name__ == "__main__":
    main()
