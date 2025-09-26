import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional


_SAFE_NAME = re.compile(r"[^A-Za-z0-9_.-]+")


def _sanitise(identifier: str) -> str:
    cleaned = _SAFE_NAME.sub("_", identifier)
    cleaned = cleaned.strip("._")
    return cleaned or "event"


class EventLogManager:
    """Manages event logs stored as JSON files on the local filesystem."""

    def __init__(
        self,
        base_path: Path,
        *,
        logger: Optional[logging.Logger] = None,
    ) -> None:
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)
        self.logger = logger or logging.getLogger(self.__class__.__name__)

    def _event_file(self, event_id: str) -> Path:
        return self.base_path / f"{_sanitise(event_id)}.json"

    def write_event_log(self, event_id: str, data: Dict[str, Any]) -> None:
        """Persist the event payload to disk."""

        payload = dict(data)
        payload["last_updated"] = datetime.now(timezone.utc).isoformat()

        event_file = self._event_file(event_id)
        with event_file.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True)

        if self.logger:
            self.logger.info("Event log written: %s", event_file)

    def read_event_log(self, event_id: str) -> Optional[Dict[str, Any]]:
        """Load an event log from disk."""

        event_file = self._event_file(event_id)
        if not event_file.exists():
            if self.logger:
                self.logger.warning("No event log found for %s", event_id)
            return None

        with event_file.open("r", encoding="utf-8") as handle:
            return json.load(handle)

    def delete_event_log(self, event_id: str) -> None:
        """Remove the stored event log."""

        event_file = self._event_file(event_id)
        try:
            event_file.unlink(missing_ok=True)
            if self.logger:
                self.logger.info("Deleted event log for %s", event_id)
        except OSError as error:
            if self.logger:
                self.logger.error("Failed to delete event log %s: %s", event_id, error)
            raise


# Example:
# manager = EventLogManager(Path("log_storage/run_history/events"))
# manager.write_event_log("123", {"status": "done"})
