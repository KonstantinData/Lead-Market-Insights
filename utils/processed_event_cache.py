"""Persistent tracker for events that have completed processing."""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


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
        if path.exists():
            try:
                raw = json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                logger.warning(
                    "Processed event cache at %s contained invalid JSON. Reinitialising.",
                    path,
                )
                raw = {}
        else:
            raw = {}

        if not isinstance(raw, dict):
            raw = {}

        raw_entries = raw.get("entries") if isinstance(raw.get("entries"), dict) else raw
        if isinstance(raw_entries, dict):
            for event_id, entry in raw_entries.items():
                if not isinstance(entry, dict):
                    continue
                fingerprint = entry.get("fingerprint")
                if not isinstance(fingerprint, str) or not fingerprint:
                    continue
                updated = entry.get("updated")
                entries[str(event_id)] = {
                    "fingerprint": fingerprint,
                    "updated": updated if isinstance(updated, str) else None,
                }

        return cls(path=path, entries=entries, dirty=False)

    def is_processed(self, event: Dict[str, Any]) -> bool:
        """Return ``True`` if *event* matches a processed entry."""

        event_id = event.get("id")
        if not isinstance(event_id, str) or not event_id:
            return False

        fingerprint, _ = self._fingerprint(event)
        entry = self.entries.get(event_id)
        if not entry:
            return False

        if entry.get("fingerprint") == fingerprint:
            return bool(entry.get("updated"))

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
            self.path.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            self.dirty = False
        except Exception:
            logger.warning(
                "Failed to flush processed event cache to %s", self.path, exc_info=True
            )

    def _fingerprint(self, event: Dict[str, Any]) -> tuple[str, Optional[str]]:
        event_id = str(event.get("id")) if event.get("id") is not None else ""
        updated = event.get("updated")
        updated_str: Optional[str]
        if isinstance(updated, str):
            updated_str = updated
        elif isinstance(updated, datetime):
            updated_str = updated.astimezone(timezone.utc).isoformat()
        else:
            updated_str = None

        summary = self._normalise_text(event.get("summary"))
        description = self._normalise_text(event.get("description"))

        base = f"{event_id}|{updated_str or '-'}|{summary}|{description}"
        fingerprint = hashlib.sha1(base.encode("utf-8")).hexdigest()
        return fingerprint, updated_str

    @staticmethod
    def _normalise_text(value: Any) -> str:
        if value is None:
            return ""
        return str(value).strip().lower()
