"""Utility helpers for initializing log managers."""

import os
from typing import Optional

from .event_log_manager import EventLogManager

__all__ = ["EventLogManager", "get_event_log_manager"]

try:  # pragma: no cover - optional dependency import
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - fallback if python-dotenv is
    # unavailable
    load_dotenv = None

if load_dotenv is not None:
    load_dotenv()


def get_event_log_manager(
    bucket_name: Optional[str] = None
) -> EventLogManager:
    """Return an :class:`EventLogManager` configured for the S3 bucket.

    Parameters
    ----------
    bucket_name:
        Optional explicit bucket name. When omitted, the value is read from the
        ``S3_BUCKET_NAME`` environment variable. The repository uses
        ``python-dotenv`` to allow configuring this variable via a
        ``.env`` file.

    Raises
    ------
    EnvironmentError
        If no bucket name can be determined.
    """

    target_bucket = bucket_name or os.getenv("S3_BUCKET_NAME")
    if not target_bucket:
        raise EnvironmentError(
            "S3 bucket name missing. Provide 'bucket_name' or set the "
            "S3_BUCKET_NAME environment variable."
        )

    return EventLogManager(target_bucket)
