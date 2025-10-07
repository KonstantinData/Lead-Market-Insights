"""Persistent tracker for events that have completed processing."""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from utils.persistence import (
    ProcessedEventsState,
    atomic_write_json,
    load_json_or_default,
)
from utils.datetime_formatting import format_cet_timestamp

logger = logging.getLogger(__name__)


SIGNIFICANT_EVENT_FIELDS = (
    "summary",
    "description",
    "location",
    "eventType",
    "creator",
    "organizer",
    "conferenceData",
    "attachments",
    "attendees",
    "extendedProperties",
)


@dataclass
class ProcessedEventCache:
    """Stores fingerprints of events that have been dispatched."""

    path: Path
    entries: Dict[str, Dict[str, Optional[str]]] = field(default_factory=dict)
    dirty: bool = False

    @classmethod
    def load(cls, path: Path) -> "ProcessedEventCache":
        """Load cache entries from *path* if it exists."""

        entries: Dict[str, Dict[str, Optional[str]]] = {}
        raw, reason = load_json_or_default(
            path,
            default=lambda: {"entries": {}},
            model=ProcessedEventsState,
        )
        if reason and reason not in {"missing"}:
            logger.warning(
                "Processed event cache at %s was reset due to %s; using default schema.",
                path,
                reason,
            )

        raw_entries = raw.get("entries") if isinstance(raw.get("entries"), dict) else raw
        if isinstance(raw_entries, dict):
            for event_id, entry in raw_entries.items():
                if not isinstance(entry, dict):
                    continue
                fingerprint = entry.get("fingerprint")
                if not isinstance(fingerprint, str) or not fingerprint:
                    continue
                updated = entry.get("updated")
                formatted_updated: Optional[str] = None
                if isinstance(updated, (str, datetime, int, float)):
                    formatted_updated = format_cet_timestamp(updated)
                if formatted_updated is None and isinstance(updated, str):
                    formatted_updated = updated
                entries[str(event_id)] = {
                    "fingerprint": fingerprint,
                    "updated": formatted_updated,
                }

        return cls(path=path, entries=entries, dirty=False)

    def is_processed(self, event: Dict[str, Any]) -> bool:
        """Return ``True`` if *event* matches a processed entry."""

        event_id = event.get("id")
        if not isinstance(event_id, str) or not event_id:
            return False

        fingerprint, updated = self._fingerprint(event)
        entry = self.entries.get(event_id)
        if not entry:
            return False

        if entry.get("fingerprint") == fingerprint:
            if updated and entry.get("updated") != updated:
                entry["updated"] = updated
                self.dirty = True
            return bool(entry.get("updated") or updated)

        # Payload changed since last dispatch; forget cached fingerprint so the
        # event will be processed again.
        self.forget(event_id)
        return False

    def mark_processed(self, event: Dict[str, Any]) -> None:
        """Persist the fingerprint for a successfully dispatched *event*."""

        event_id = event.get("id")
        if not isinstance(event_id, str) or not event_id:
            return

        fingerprint, updated = self._fingerprint(event)
        if not updated:
            # Without an ``updated`` timestamp we cannot reliably deduplicate.
            self.forget(event_id)
            return

        entry = {"fingerprint": fingerprint, "updated": updated}
        if self.entries.get(event_id) != entry:
            self.entries[event_id] = entry
            self.dirty = True

    def forget(self, event_id: Optional[str]) -> None:
        if not isinstance(event_id, str) or not event_id:
            return

        if event_id in self.entries:
            del self.entries[event_id]
            self.dirty = True

    def flush(self) -> None:
        if not self.dirty:
            return

        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            payload = {"entries": self.entries}
            atomic_write_json(self.path, payload, model=ProcessedEventsState)
            self.dirty = False
        except Exception:
            logger.warning(
                "Failed to flush processed event cache to %s", self.path, exc_info=True
            )

    def _fingerprint(self, event: Dict[str, Any]) -> tuple[str, Optional[str]]:
        event_id = str(event.get("id")) if event.get("id") is not None else ""
        updated = event.get("updated")
        updated_str: Optional[str] = None
        if isinstance(updated, (str, datetime, int, float)):
            updated_str = format_cet_timestamp(updated)
            if updated_str is None and isinstance(updated, str):
                updated_str = updated

        payload_segments = [event_id]
        for key in SIGNIFICANT_EVENT_FIELDS:
            payload_segments.append(
                f"{key}:{self._normalise_structure(event.get(key))}"
            )

        base = "|".join(payload_segments)
        fingerprint = hashlib.sha1(base.encode("utf-8")).hexdigest()
        return fingerprint, updated_str

    @staticmethod
    def _normalise_text(value: Any) -> str:
        if value is None:
            return ""
        return str(value).strip().lower()

    @classmethod
    def _normalise_structure(cls, value: Any) -> str:
        if value is None:
            return ""
        if isinstance(value, str):
            return cls._normalise_text(value)
        if isinstance(value, bool):
            return "true" if value else "false"
        if isinstance(value, (int, float)):
            return str(value)
        if isinstance(value, dict):
            items = []
            for key in sorted(value.keys(), key=str):
                items.append(
                    f"{cls._normalise_text(key)}:{cls._normalise_structure(value[key])}"
                )
            return "{" + "|".join(items) + "}"
        if isinstance(value, (list, tuple, set)):
            parts = [cls._normalise_structure(item) for item in value]
            parts.sort()
            return "[" + "|".join(parts) + "]"
        return cls._normalise_text(value)
