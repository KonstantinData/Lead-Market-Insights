"""Helpers for consistent Europe/Berlin date and time formatting."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Union

try:  # pragma: no cover - zoneinfo is available from Python 3.9+
    from zoneinfo import ZoneInfo
except ImportError:  # pragma: no cover - fallback for alternative runtimes
    ZoneInfo = None  # type: ignore[assignment]

if ZoneInfo is not None:  # pragma: no branch
    _BERLIN = ZoneInfo("Europe/Berlin")
else:  # pragma: no cover - exercised only when zoneinfo is unavailable
    _BERLIN = timezone(timedelta(hours=1))

_DATETIME_FORMAT = "%Y-%m-%d %H:%M"


def _ensure_datetime(value: Union[str, datetime]) -> Union[datetime, None]:
    """Normalise *value* to an aware :class:`~datetime.datetime` when possible."""

    if isinstance(value, datetime):
        candidate = value
    else:
        try:
            candidate = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except Exception:  # pragma: no cover - defensive fallback for custom inputs
            return None

    if candidate.tzinfo is None:
        candidate = candidate.replace(tzinfo=timezone.utc)

    return candidate


def current_berlin_timestamp() -> str:
    """Return the current time formatted for the Europe/Berlin timezone."""

    return format_report_datetime(datetime.now(tz=_BERLIN))


def format_report_datetime(value: Union[str, datetime]) -> str:
    """Format *value* using the Europe/Berlin specification.

    Parameters
    ----------
    value:
        A datetime object or ISO-8601 like string representing the timestamp.

    Returns
    -------
    str
        Timestamp formatted as ``YYYY-MM-DD HH:MM``. Unparseable inputs are
        returned unchanged so calling code can decide how to handle them.
    """

    candidate = _ensure_datetime(value)
    if candidate is None:
        return str(value)

    berlin_timestamp = candidate.astimezone(_BERLIN)
    return berlin_timestamp.strftime(_DATETIME_FORMAT)


__all__ = ["current_berlin_timestamp", "format_report_datetime"]
