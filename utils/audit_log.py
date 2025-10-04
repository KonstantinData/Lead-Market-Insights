"""Audit log helper for recording human-in-the-loop interactions."""

from __future__ import annotations

import json
import logging
import threading
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional


@dataclass
class AuditRecord:
    """Structured representation of a single audit entry."""

    audit_id: str
    timestamp: str
    event_id: Optional[str]
    request_type: str
    stage: str
    responder: str
    outcome: str
    payload: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert the record to a JSON serialisable dictionary."""

        data = asdict(self)
        if self.payload is None:
            data.pop("payload", None)
        return data


class AuditLog:
    """Light-weight JSONL audit log writer/reader."""

    def __init__(
        self,
        log_path: Path,
        *,
        logger: Optional[logging.Logger] = None,
    ) -> None:
        self.log_path = Path(log_path)
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        self.logger = logger or logging.getLogger(self.__class__.__name__)
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # Record helpers
    # ------------------------------------------------------------------
    def record(
        self,
        *,
        event_id: Optional[str],
        request_type: str,
        stage: str,
        responder: str,
        outcome: str,
        payload: Optional[Dict[str, Any]] = None,
        audit_id: Optional[str] = None,
    ) -> str:
        """Append a structured audit record to the JSONL log.

        Parameters
        ----------
        event_id:
            Identifier of the event the entry pertains to.
        request_type:
            Category of human-in-the-loop request (e.g. ``dossier_confirmation``).
        stage:
            Lifecycle stage for the record (e.g. ``request`` or ``response``).
        responder:
            The party that initiated or answered the request.
        outcome:
            Summary of the outcome for this stage.
        payload:
            Optional structured payload for debugging.
        audit_id:
            When provided, associate the entry with an existing request. If omitted
            a new audit id is generated and returned.
        """

        entry_id = audit_id or uuid.uuid4().hex
        record = AuditRecord(
            audit_id=entry_id,
            timestamp=datetime.now(timezone.utc).isoformat(),
            event_id=event_id,
            request_type=request_type,
            stage=stage,
            responder=responder,
            outcome=outcome,
            payload=payload,
        )

        with self._lock:
            with self.log_path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(record.to_dict(), ensure_ascii=False))
                handle.write("\n")

        self.logger.debug(
            "Recorded audit entry %s (%s/%s) outcome=%s",
            entry_id,
            request_type,
            stage,
            outcome,
        )
        return entry_id

    # ------------------------------------------------------------------
    # Reader helpers – primarily for tests/debugging
    # ------------------------------------------------------------------
    def iter_entries(self) -> Iterator[Dict[str, Any]]:
        """Yield entries from the JSONL audit log if it exists."""

        if not self.log_path.exists():
            return
        with self.log_path.open("r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    yield json.loads(line)
                except json.JSONDecodeError:
                    self.logger.warning(
                        "Skipping invalid audit log line in %s: %s", self.log_path, line
                    )

    def load_entries(self) -> List[Dict[str, Any]]:
        """Return all audit log entries as a list."""

        return list(self.iter_entries())

    def has_response(self, audit_id: str) -> bool:
        """Return ``True`` when a response entry exists for *audit_id*."""

        if not audit_id:
            return False

        for entry in self.iter_entries():
            if (
                entry.get("audit_id") == audit_id
                and entry.get("stage") == "response"
            ):
                return True
        return False
