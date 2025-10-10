"""
Append-only audit log (JSONL) with hash chaining.
"""
from __future__ import annotations
import json, hashlib
from pathlib import Path
from typing import Optional
from .contracts import AuditEvent
from .logging_setup import get_logger


DATA_DIR = Path("./data")
DATA_DIR.mkdir(parents=True, exist_ok=True)
AUDIT_PATH = DATA_DIR / "audit.jsonl"
log = get_logger("hitl.audit", "audit_log.log")


class AuditLog:
# Explanation: write events and maintain tail hash for tamper-evidence
def __init__(self, path: Path = AUDIT_PATH):
self.path = path
self._tail_hash: Optional[str] = self._load_tail()


def _load_tail(self) -> Optional[str]:
if not self.path.exists():
return None
tail = None
with self.path.open("r", encoding="utf-8") as f:
for line in f:
try:
obj = json.loads(line)
tail = obj.get("hash")
except Exception as e:
log.error("audit_load_error", extra={"error": str(e)})
return tail


def append(self, ev: AuditEvent) -> str:
payload = ev.model_dump(mode="json")
prev = self._tail_hash
encoded = json.dumps({"prev_hash": prev, "event": payload}, ensure_ascii=False)
h = hashlib.sha256(encoded.encode("utf-8")).hexdigest()
record = {"prev_hash": prev, "hash": h, **payload}
with self.path.open("a", encoding="utf-8") as f:
f.write(json.dumps(record, ensure_ascii=False) + "\n")
self._tail_hash = h
log.info("audit_appended", extra={"event": ev.event, "run_id": ev.run_id, "hash": h})
return h