"""Extract HTML tables directly into pandas DataFrames."""

from __future__ import annotations

from io import StringIO

import pandas as pd
from bs4 import BeautifulSoup


class TableParser:
    """Parse <table> elements from HTML into DataFrames."""

    def parse_all(self, html: str) -> list[pd.DataFrame]:
        """Return a DataFrame for every table found on the page."""
        return pd.read_html(StringIO(html))

    def parse_by_index(self, html: str, index: int = 0) -> pd.DataFrame:
        tables = pd.read_html(StringIO(html))
        if not tables:
            raise ValueError("No tables found on the page.")
        if index >= len(tables):
            raise IndexError(f"Table index {index} out of range ({len(tables)} tables found).")
        return tables[index]

    def parse_by_id(self, html: str, table_id: str) -> pd.DataFrame:
        soup = BeautifulSoup(html, "lxml")
        tag = soup.find("table", {"id": table_id})
        if tag is None:
            raise ValueError(f"No <table id='{table_id}'> found.")
        return pd.read_html(StringIO(str(tag)))[0]

    def parse_by_css(self, html: str, selector: str) -> pd.DataFrame:
        soup = BeautifulSoup(html, "lxml")
        tag = soup.select_one(selector)
        if tag is None:
            raise ValueError(f"No element matching '{selector}' found.")
        return pd.read_html(StringIO(str(tag)))[0]
