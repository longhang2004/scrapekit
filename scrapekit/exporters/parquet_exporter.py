from __future__ import annotations

from pathlib import Path
from typing import Literal

import pandas as pd

from scrapekit.exporters.base import BaseExporter


class ParquetExporter(BaseExporter):
    """Parquet exporter — ideal for large datasets and analytics pipelines."""

    extension = "parquet"

    def __init__(
        self,
        output_dir: str | Path = "./output",
        compression: Literal["snappy", "gzip", "brotli", "none"] = "snappy",
    ) -> None:
        super().__init__(output_dir)
        self._compression = compression

    def _write(self, df: pd.DataFrame, path: Path) -> None:
        df.to_parquet(path, compression=self._compression, index=False)
