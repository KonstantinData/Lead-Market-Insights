"""Helpers for consistent CET date and time formatting in reports."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Union

try:  # pragma: no cover - zoneinfo is available from Python 3.9+
    from zoneinfo import ZoneInfo
except ImportError:  # pragma: no cover - fallback for alternative runtimes
    ZoneInfo = None  # type: ignore[assignment]

if ZoneInfo is not None:  # pragma: no branch
    _CET = ZoneInfo("CET")
else:  # pragma: no cover - exercised only when zoneinfo is unavailable
    _CET = timezone(timedelta(hours=1))

_DATETIME_FORMAT = "%d.%m.%Y %H:%M CET"


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


__all__ = ["format_report_datetime"]
