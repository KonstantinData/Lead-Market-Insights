"""Utility helpers for initializing log managers backed by local storage."""

from pathlib import Path
from typing import Optional

from .event_log_manager import EventLogManager
from config.config import settings

__all__ = ["EventLogManager", "get_event_log_manager"]

try:  # pragma: no cover - optional dependency import
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - fallback if python-dotenv is unavailable
    load_dotenv = None

if load_dotenv is not None:
    load_dotenv()


def get_event_log_manager(base_path: Optional[Path] = None) -> EventLogManager:
    """Return an :class:`EventLogManager` configured for local storage."""

    target_path = Path(base_path) if base_path is not None else settings.event_log_dir
    return EventLogManager(target_path)
