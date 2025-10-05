"""Negative event cache to avoid reprocessing unchanged events without triggers."""

from __future__ import annotations

import hashlib
import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from utils.persistence import atomic_write_json

logger = logging.getLogger(__name__)


NEG_CACHE_VERSION = 1
NEG_CACHE_MAX_AGE_DAYS = 30
NEG_CACHE_MAX_AGE_SECONDS = NEG_CACHE_MAX_AGE_DAYS * 24 * 60 * 60


def _parse_iso_timestamp(value: str) -> Optional[datetime]:
    """Best effort ISO8601 parser supporting ``Z`` suffixes."""

    if not value:
        return None

    try:
        if value.endswith("Z"):
            value = value[:-1] + "+00:00"
        return datetime.fromisoformat(value)
    except ValueError:
        logger.debug("Unable to parse timestamp '%s' in negative cache", value)
        return None


@dataclass
class NegativeEventCache:
    """Caches skip decisions for events without triggers."""

    path: Path
    entries: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    dirty: bool = False
    classification_version: str = "v1"

    @classmethod
    def load(
        cls,
        path: Path,
        *,
        rule_hash: str,
        now: Optional[float] = None,
    ) -> "NegativeEventCache":
        """Load cache from disk applying retention rules."""

        now = now or time.time()
        entries: Dict[str, Dict[str, Any]] = {}

        if path.exists():
            try:
                raw = json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                logger.warning(
                    "Negative cache at %s contained invalid JSON. Reinitialising.", path
                )
                raw = {}
        else:
            raw = {}

        if not isinstance(raw, dict):
            raw = {}

        raw_entries = raw.get("entries") if isinstance(raw.get("entries"), dict) else {}

        for event_id, entry in raw_entries.items():
            if not isinstance(entry, dict):
                continue
            fingerprint = entry.get("fingerprint")
            if not isinstance(fingerprint, str) or not fingerprint:
                continue

            updated = entry.get("updated")
            last_seen = entry.get("last_seen")

            if not cls._is_entry_fresh(updated, last_seen, now):
                continue

            entries[str(event_id)] = {
                "fingerprint": fingerprint,
                "updated": updated if isinstance(updated, str) else None,
                "rule_hash": entry.get("rule_hash"),
                "decision": entry.get("decision"),
                "first_seen": entry.get("first_seen"),
                "last_seen": last_seen if isinstance(last_seen, (int, float)) else None,
                "classification_version": entry.get("classification_version", "v1"),
            }

        cache = cls(path=path, entries=entries, dirty=False)
        cache._purge_stale(now)  # noqa: SLF001
        return cache

    def should_skip(self, event: Dict[str, Any], rule_hash: str) -> bool:
        """Return ``True`` if the event can be skipped based on cached decision."""

        event_id = event.get("id")
        if not event_id or not isinstance(event_id, str):
            return False

        fingerprint, _ = self._fingerprint(event)
        entry = self.entries.get(event_id)
        if not entry:
            return False

        if entry.get("rule_hash") != rule_hash:
            return False

        if entry.get("fingerprint") != fingerprint:
            return False

        if entry.get("decision") not in {"no_trigger", "skipped_trigger_threshold"}:
            return False

        last_seen = entry.get("last_seen")
        now = time.time()
        if not self._is_entry_fresh(entry.get("updated"), last_seen, now):
            # Entry is stale; purge and continue processing event.
            self.forget(event_id)
            return False

        if not entry.get("updated"):
            entry["last_seen"] = now
            self.dirty = True

        return True

    def get_decision(self, event_id: Optional[str]) -> Optional[str]:
        if not event_id:
            return None
        entry = self.entries.get(event_id)
        if entry:
            return entry.get("decision")
        return None

    def record_no_trigger(
        self, event: Dict[str, Any], rule_hash: str, decision: str
    ) -> None:
        event_id = event.get("id")
        if not event_id or not isinstance(event_id, str):
            return

        fingerprint, updated = self._fingerprint(event)
        now = time.time()

        entry = self.entries.get(event_id, {})
        first_seen = entry.get("first_seen", now)

        new_entry = {
            "fingerprint": fingerprint,
            "updated": updated,
            "rule_hash": rule_hash,
            "decision": decision,
            "first_seen": first_seen,
            "last_seen": now if not updated else entry.get("last_seen", now),
            "classification_version": self.classification_version,
        }

        if self.entries.get(event_id) != new_entry:
            self.entries[event_id] = new_entry
            self.dirty = True

    def forget(self, event_id: Optional[str]) -> None:
        if not event_id or not isinstance(event_id, str):
            return

        if event_id in self.entries:
            del self.entries[event_id]
            self.dirty = True

    def flush(self) -> None:
        if not self.dirty:
            return

        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            payload = {
                "version": NEG_CACHE_VERSION,
                "entries": self.entries,
            }
            atomic_write_json(self.path, payload)
            self.dirty = False
        except Exception:
            logger.warning(
                "Failed to flush negative cache to %s", self.path, exc_info=True
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

    def _purge_stale(self, now: Optional[float] = None) -> None:
        now = now or time.time()
        removed = [
            event_id
            for event_id, entry in list(self.entries.items())
            if not self._is_entry_fresh(
                entry.get("updated"), entry.get("last_seen"), now
            )
        ]
        for event_id in removed:
            del self.entries[event_id]
            self.dirty = True

    @staticmethod
    def _is_entry_fresh(
        updated: Optional[str], last_seen: Optional[float], now: float
    ) -> bool:
        if updated:
            parsed = _parse_iso_timestamp(updated)
            if parsed is not None:
                if parsed.tzinfo is None:
                    parsed = parsed.replace(tzinfo=timezone.utc)
                age = now - parsed.timestamp()
                return age <= NEG_CACHE_MAX_AGE_SECONDS

        if last_seen is not None:
            age = now - float(last_seen)
            return age <= NEG_CACHE_MAX_AGE_SECONDS

        return True
