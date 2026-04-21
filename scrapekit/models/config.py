"""Pydantic models for configuration validation."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, Field, HttpUrl, model_validator


class PaginationConfig(BaseModel):
    enabled: bool = False
    max_pages: int = Field(default=10, ge=1)
    next_selector: str = "a.next"


class FieldConfig(BaseModel):
    selector: str
    attribute: str | None = None  # None → inner text


class ParserConfig(BaseModel):
    item_selector: str = "body"
    fields: dict[str, FieldConfig] = Field(default_factory=dict)


class ScraperConfig(BaseModel):
    base_url: str
    timeout: int = Field(default=30, ge=1, le=300)
    max_retries: int = Field(default=3, ge=0, le=10)
    retry_delay: float = Field(default=2.0, ge=0)
    delay_between_requests: float = Field(default=1.0, ge=0)
    delay_jitter: float = Field(default=0.3, ge=0)
    max_concurrent_requests: int = Field(default=5, ge=1, le=50)
    proxies: list[str] = Field(default_factory=list)
    headers: dict[str, str] = Field(default_factory=dict)
    pagination: PaginationConfig = Field(default_factory=PaginationConfig)

    @model_validator(mode="before")
    @classmethod
    def set_default_user_agent(cls, values: dict[str, Any]) -> dict[str, Any]:
        headers = values.get("headers", {})
        if "User-Agent" not in headers:
            headers["User-Agent"] = (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            )
            values["headers"] = headers
        return values


ExportFormat = Literal["csv", "json", "excel", "sqlite", "parquet"]


class ExportConfig(BaseModel):
    formats: list[ExportFormat] = Field(default=["csv", "json"])
    output_dir: Path = Field(default=Path("./output"))
    filename_prefix: str = "scraped_data"
    dedup_field: str | None = None

    @model_validator(mode="after")
    def create_output_dir(self) -> "ExportConfig":
        self.output_dir.mkdir(parents=True, exist_ok=True)
        return self


class LoggingConfig(BaseModel):
    level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    file: str | None = "logs/scrapekit.log"
    rotation: str = "10 MB"


class AppConfig(BaseModel):
    scraper: ScraperConfig
    parser: ParserConfig = Field(default_factory=ParserConfig)
    export: ExportConfig = Field(default_factory=ExportConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)

    @classmethod
    def from_yaml(cls, path: str | Path) -> "AppConfig":
        with open(path) as f:
            data = yaml.safe_load(f)
        return cls(**data)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AppConfig":
        return cls(**data)
