"""Helpers for consistent CET date and time formatting across the project."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional, Union

try:  # pragma: no cover - zoneinfo is available from Python 3.9+
    from zoneinfo import ZoneInfo
except ImportError:  # pragma: no cover - fallback for alternative runtimes
    ZoneInfo = None  # type: ignore[assignment]

if ZoneInfo is not None:  # pragma: no branch
    _CET = ZoneInfo("Europe/Berlin")
else:  # pragma: no cover - exercised only when zoneinfo is unavailable
    _CET = timezone(timedelta(hours=1))

_DATETIME_FORMAT = "%d.%m.%Y %H:%M CET"
_LOG_DATETIME_FORMAT = "%Y-%m-%d %H:%M:%S"


def _ensure_datetime(value: Union[str, datetime, int, float]) -> Optional[datetime]:
    """Normalise *value* to an aware :class:`~datetime.datetime` when possible."""

    if isinstance(value, datetime):
        candidate = value
    elif isinstance(value, (int, float)):
        candidate = datetime.fromtimestamp(value, tz=timezone.utc)
    else:
        try:
            candidate = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except Exception:  # pragma: no cover - defensive fallback for custom inputs
            return None

    if candidate.tzinfo is None:
        candidate = candidate.replace(tzinfo=timezone.utc)

    return candidate


def format_report_datetime(value: Union[str, datetime]) -> str:
    """Format *value* using the CET report specification.

    Parameters
    ----------
    value:
        A datetime object or ISO-8601 like string representing the timestamp.

    Returns
    -------
    str
        Timestamp formatted as ``TT.MM.JJJJ HH:MM CET``. Unparseable inputs are
        returned unchanged so calling code can decide how to handle them.
    """

    candidate = _ensure_datetime(value)
    if candidate is None:
        return str(value)

    cet_timestamp = candidate.astimezone(_CET)
    return cet_timestamp.strftime(_DATETIME_FORMAT)


def format_cet_timestamp(value: Union[str, datetime, int, float]) -> Optional[str]:
    """Return *value* formatted as ``YYYY-MM-DD HH:MM:SS`` in CET."""

    candidate = _ensure_datetime(value)
    if candidate is None:
        return None

    return candidate.astimezone(_CET).strftime(_LOG_DATETIME_FORMAT)


def now_cet_timestamp() -> str:
    """Return the current CET time formatted for logging."""

    return datetime.now(_CET).strftime(_LOG_DATETIME_FORMAT)


LOG_TIMESTAMP_FORMAT = _LOG_DATETIME_FORMAT
CET_ZONE = _CET


__all__ = [
    "format_report_datetime",
    "format_cet_timestamp",
    "now_cet_timestamp",
    "LOG_TIMESTAMP_FORMAT",
    "CET_ZONE",
]
