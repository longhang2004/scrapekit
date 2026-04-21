"""Tests for all exporter classes."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pandas as pd
import pytest

from scrapekit.exporters import (
    CSVExporter,
    JSONExporter,
    ExcelExporter,
    SQLiteExporter,
    ParquetExporter,
)

SAMPLE_DATA = [
    {"name": "Alice", "age": 30, "city": "New York"},
    {"name": "Bob", "age": 25, "city": "London"},
    {"name": "Carol", "age": 35, "city": "Tokyo"},
]


@pytest.fixture()
def tmp_output(tmp_path: Path) -> Path:
    return tmp_path


class TestCSVExporter:
    def test_creates_file(self, tmp_output: Path) -> None:
        path = CSVExporter(tmp_output).export(SAMPLE_DATA, "test")
        assert path.exists()
        assert path.suffix == ".csv"

    def test_row_count(self, tmp_output: Path) -> None:
        path = CSVExporter(tmp_output).export(SAMPLE_DATA, "test")
        df = pd.read_csv(path)
        assert len(df) == len(SAMPLE_DATA)

    def test_columns(self, tmp_output: Path) -> None:
        path = CSVExporter(tmp_output).export(SAMPLE_DATA, "test")
        df = pd.read_csv(path)
        assert list(df.columns) == ["name", "age", "city"]

    def test_empty_data_raises(self, tmp_output: Path) -> None:
        with pytest.raises(ValueError):
            CSVExporter(tmp_output).export([], "test")


class TestJSONExporter:
    def test_creates_file(self, tmp_output: Path) -> None:
        path = JSONExporter(tmp_output).export(SAMPLE_DATA, "test")
        assert path.exists()
        assert path.suffix == ".json"

    def test_valid_json(self, tmp_output: Path) -> None:
        import json
        path = JSONExporter(tmp_output).export(SAMPLE_DATA, "test")
        with open(path) as f:
            data = json.load(f)
        assert len(data) == len(SAMPLE_DATA)
        assert data[0]["name"] == "Alice"


class TestExcelExporter:
    def test_creates_file(self, tmp_output: Path) -> None:
        path = ExcelExporter(tmp_output).export(SAMPLE_DATA, "test")
        assert path.exists()
        assert path.suffix == ".xlsx"

    def test_row_count(self, tmp_output: Path) -> None:
        path = ExcelExporter(tmp_output).export(SAMPLE_DATA, "test")
        df = pd.read_excel(path)
        assert len(df) == len(SAMPLE_DATA)


class TestSQLiteExporter:
    def test_creates_db(self, tmp_output: Path) -> None:
        path = SQLiteExporter(tmp_output, table_name="people").export(SAMPLE_DATA, "test")
        assert path.exists()
        assert path.suffix == ".db"

    def test_queryable(self, tmp_output: Path) -> None:
        exporter = SQLiteExporter(tmp_output, table_name="people")
        path = exporter.export(SAMPLE_DATA, "test")
        df = exporter.query(path, "SELECT * FROM people WHERE age > 28")
        assert len(df) == 2

    def test_replace_mode(self, tmp_output: Path) -> None:
        exporter = SQLiteExporter(tmp_output, table_name="data", if_exists="replace")
        exporter.export(SAMPLE_DATA, "test")
        path = exporter.export(SAMPLE_DATA, "test")
        df = exporter.query(path, "SELECT * FROM data")
        assert len(df) == len(SAMPLE_DATA)


class TestParquetExporter:
    def test_creates_file(self, tmp_output: Path) -> None:
        path = ParquetExporter(tmp_output).export(SAMPLE_DATA, "test")
        assert path.exists()
        assert path.suffix == ".parquet"

    def test_readable(self, tmp_output: Path) -> None:
        path = ParquetExporter(tmp_output).export(SAMPLE_DATA, "test")
        df = pd.read_parquet(path)
        assert len(df) == len(SAMPLE_DATA)
