from __future__ import annotations

from pathlib import Path

import pandas as pd

from scrapekit.exporters.base import BaseExporter


class CSVExporter(BaseExporter):
    extension = "csv"

    def __init__(
        self,
        output_dir: str | Path = "./output",
        encoding: str = "utf-8-sig",
        separator: str = ",",
    ) -> None:
        super().__init__(output_dir)
        self._encoding = encoding
        self._sep = separator

    def _write(self, df: pd.DataFrame, path: Path) -> None:
        df.to_csv(path, index=False, encoding=self._encoding, sep=self._sep)
