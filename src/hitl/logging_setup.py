"""Utility helpers for namespaced HITL loggers."""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path


LOG_DIR = Path("./log_storage")
LOG_DIR.mkdir(parents=True, exist_ok=True)

_DEF_FMT = "%(asctime)s %(levelname)s %(name)s %(message)s"


def get_logger(name: str, filename: str) -> logging.Logger:
    """Return a logger that writes to ``log_storage`` without touching globals."""

    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    logfile = LOG_DIR / filename

    already_configured = any(
        isinstance(handler, RotatingFileHandler)
        and getattr(handler, "baseFilename", "") == str(logfile)
        for handler in logger.handlers
    )
    if not already_configured:
        handler = RotatingFileHandler(
            str(logfile), maxBytes=5_000_000, backupCount=3, encoding="utf-8"
        )
        handler.setFormatter(logging.Formatter(_DEF_FMT))
        logger.addHandler(handler)
        logger.propagate = False

    return logger