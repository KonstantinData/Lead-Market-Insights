"""Append-only audit log used by the standalone HITL components."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Optional

from .contracts import AuditEvent
from .logging_setup import get_logger


DATA_DIR = Path("./data")
DATA_DIR.mkdir(parents=True, exist_ok=True)

AUDIT_PATH = DATA_DIR / "audit.jsonl"
log = get_logger("hitl.audit", "audit_log.log")


class AuditLog:
    """Persist audit events with a simple hash chain for tamper evidence."""

    def __init__(self, path: Path = AUDIT_PATH) -> None:
        self.path = path
        self._tail_hash: Optional[str] = self._load_tail()

    def _load_tail(self) -> Optional[str]:
        if not self.path.exists():
            return None

        tail: Optional[str] = None
        try:
            with self.path.open("r", encoding="utf-8") as handle:
                for line in handle:
                    try:
                        payload = json.loads(line)
                    except json.JSONDecodeError:
                        log.warning("discarding malformed audit entry", extra={"line": line})
                        continue
                    tail = payload.get("hash")
        except OSError:
            log.exception("failed to read audit log tail")
        return tail

    def append(self, event: AuditEvent) -> str:
        payload = event.model_dump(mode="json")
        prev_hash = self._tail_hash
        encoded = json.dumps({"prev_hash": prev_hash, "event": payload}, ensure_ascii=False)
        digest = hashlib.sha256(encoded.encode("utf-8")).hexdigest()
        record = {"prev_hash": prev_hash, "hash": digest, **payload}

        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")

        self._tail_hash = digest
        log.info(
            "audit_appended",
            extra={"event": event.event, "run_id": event.run_id, "hash": digest},
        )
        return digest