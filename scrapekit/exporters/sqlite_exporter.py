from __future__ import annotations

import sqlite3
from pathlib import Path

import pandas as pd

from scrapekit.exporters.base import BaseExporter


class SQLiteExporter(BaseExporter):
    """Export data to a SQLite database — one table per export call."""

    extension = "db"

    def __init__(
        self,
        output_dir: str | Path = "./output",
        table_name: str = "scraped_data",
        if_exists: str = "replace",
    ) -> None:
        super().__init__(output_dir)
        self._table = table_name
        self._if_exists = if_exists

    def _write(self, df: pd.DataFrame, path: Path) -> None:
        conn = sqlite3.connect(path)
        try:
            df.to_sql(self._table, conn, if_exists=self._if_exists, index=False)
            conn.commit()
        finally:
            conn.close()

    def query(self, db_path: str | Path, sql: str) -> pd.DataFrame:
        conn = sqlite3.connect(db_path)
        try:
            return pd.read_sql_query(sql, conn)
        finally:
            conn.close()
