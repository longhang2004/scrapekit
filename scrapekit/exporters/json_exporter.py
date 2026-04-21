from __future__ import annotations

from pathlib import Path
from typing import Literal

import pandas as pd

from scrapekit.exporters.base import BaseExporter


class JSONExporter(BaseExporter):
    extension = "json"

    def __init__(
        self,
        output_dir: str | Path = "./output",
        orient: Literal["records", "split", "index", "columns", "values"] = "records",
        indent: int = 2,
    ) -> None:
        super().__init__(output_dir)
        self._orient = orient
        self._indent = indent

    def _write(self, df: pd.DataFrame, path: Path) -> None:
        df.to_json(path, orient=self._orient, indent=self._indent, force_ascii=False)
