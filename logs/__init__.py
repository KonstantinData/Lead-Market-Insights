"""Utility helpers for initializing log managers backed by PostgreSQL."""

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


def get_event_log_manager(
    dsn: Optional[str] = None,
    *,
    table_name: Optional[str] = None,
) -> EventLogManager:
    """Return an :class:`EventLogManager` configured for PostgreSQL storage.

    Parameters
    ----------
    dsn:
        Optional explicit PostgreSQL DSN. When omitted, the value is read from
        the ``POSTGRES_DSN`` (or ``DATABASE_URL``) environment variable.
    table_name:
        Optional table override. Defaults to the value configured via the
        ``POSTGRES_EVENT_LOG_TABLE`` environment variable or ``event_logs``.

    Raises
    ------
    EnvironmentError
        If no DSN can be determined.
    """

    target_dsn = dsn or settings.postgres_dsn
    if not target_dsn:
        raise EnvironmentError(
            "PostgreSQL DSN missing. Provide 'dsn' or set the POSTGRES_DSN "
            "(or DATABASE_URL) environment variable."
        )

    target_table = table_name or settings.postgres_event_log_table
    return EventLogManager(target_dsn, table_name=target_table)

