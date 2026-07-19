from __future__ import annotations

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path


def configure_logging(
    log_file: str | Path,
    *,
    level: str = "INFO",
    max_bytes: int = 5_000_000,
    backup_count: int = 5,
) -> logging.Logger:
    normalized_level = level.upper().strip()
    numeric_level = getattr(logging, normalized_level, None)
    if not isinstance(numeric_level, int):
        raise ValueError(f"Unsupported log level: {level}.")
    if max_bytes < 1:
        raise ValueError("Log max_bytes must be positive.")
    if backup_count < 1:
        raise ValueError("Log backup_count must be positive.")

    path = Path(log_file)
    path.parent.mkdir(parents=True, exist_ok=True)
    formatter = logging.Formatter(
        "%(asctime)s %(levelname)s %(name)s %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S%z",
    )
    logger = logging.getLogger("jobmonitor")
    logger.setLevel(numeric_level)
    logger.propagate = False
    for handler in logger.handlers:
        handler.close()
    logger.handlers.clear()

    file_handler = RotatingFileHandler(
        path,
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    return logger
