"""Abstract base class for all exporters."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

import pandas as pd


class BaseExporter(ABC):
    """Common interface every exporter must implement."""

    extension: str = ""

    def __init__(self, output_dir: str | Path = "./output") -> None:
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def export(self, data: list[dict[str, Any]], filename: str) -> Path:
        """Convert *data* to a DataFrame, deduplicate if needed, write to disk."""
        if not data:
            raise ValueError("No data to export.")
        df = pd.DataFrame(data)
        output_path = self.output_dir / f"{filename}.{self.extension}"
        self._write(df, output_path)
        return output_path

    def export_dataframe(self, df: pd.DataFrame, filename: str) -> Path:
        output_path = self.output_dir / f"{filename}.{self.extension}"
        self._write(df, output_path)
        return output_path

    @abstractmethod
    def _write(self, df: pd.DataFrame, path: Path) -> None: ...
