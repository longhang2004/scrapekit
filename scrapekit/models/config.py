"""Pydantic models for configuration validation."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, Field, model_validator


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

    # --- Delay / rate-limiting ---
    # Preferred: use min_delay + max_delay for a uniform random window.
    # Legacy: delay_between_requests + delay_jitter still accepted.
    min_delay: float = Field(default=1.0, ge=0, description="Minimum delay between requests (seconds).")
    max_delay: float = Field(default=2.0, ge=0, description="Maximum delay between requests (seconds).")
    # kept for backwards-compat; if set they override min/max_delay
    delay_between_requests: float | None = Field(default=None, ge=0)
    delay_jitter: float | None = Field(default=None, ge=0)

    max_concurrent_requests: int = Field(default=5, ge=1, le=50)
    proxies: list[str] = Field(default_factory=list)
    headers: dict[str, str] = Field(default_factory=dict)
    pagination: PaginationConfig = Field(default_factory=PaginationConfig)

    # --- Anti-ban ---
    rotate_user_agent: bool = Field(default=True, description="Randomly rotate User-Agent per request.")
    ban_indicator: str | None = Field(
        default=None,
        description="If this string appears in any response body, treat it as a soft-ban and raise.",
    )
    respect_robots_txt: bool = Field(default=False, description="Honour robots.txt disallow rules.")

    @model_validator(mode="before")
    @classmethod
    def _normalise_delays(cls, values: dict[str, Any]) -> dict[str, Any]:
        """Back-compat: convert legacy delay_between_requests/delay_jitter to min/max_delay."""
        dbrq = values.get("delay_between_requests")
        jitter = values.get("delay_jitter")
        if dbrq is not None and "min_delay" not in values:
            values["min_delay"] = float(dbrq)
            values["max_delay"] = float(dbrq) + float(jitter or 0.3)
        return values

    @model_validator(mode="before")
    @classmethod
    def _set_default_headers(cls, values: dict[str, Any]) -> dict[str, Any]:
        """Seed realistic browser headers when none are provided."""
        headers = values.get("headers", {})
        if not headers.get("Accept"):
            headers.setdefault(
                "Accept",
                "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            )
        if not headers.get("Accept-Language"):
            headers.setdefault("Accept-Language", "en-US,en;q=0.9")
        if not headers.get("Accept-Encoding"):
            headers.setdefault("Accept-Encoding", "gzip, deflate, br")
        if not headers.get("Connection"):
            headers.setdefault("Connection", "keep-alive")
        if not headers.get("Upgrade-Insecure-Requests"):
            headers.setdefault("Upgrade-Insecure-Requests", "1")
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
