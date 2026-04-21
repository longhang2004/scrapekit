"""Centralised logging via loguru with optional file rotation."""

from __future__ import annotations

import sys
from pathlib import Path

from loguru import logger


def get_logger(
    name: str = "scrapekit",
    level: str = "INFO",
    log_file: str | None = None,
    rotation: str = "10 MB",
) -> "logger":
    logger.remove()
    logger.add(
        sys.stderr,
        level=level,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan> - <level>{message}</level>",
    )
    if log_file:
        Path(log_file).parent.mkdir(parents=True, exist_ok=True)
        logger.add(log_file, level=level, rotation=rotation, retention="30 days", compression="zip")
    return logger.bind(scraper=name)
