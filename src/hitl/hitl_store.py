"""
Append-only HITL state (JSONL) with in-memory index by run_id.
"""
from __future__ import annotations
import json
from pathlib import Path
from typing import Dict, Any, Optional
from dataclasses import dataclass
from .contracts import HitlRequest, HitlDecision
from .logging_setup import get_logger


DATA_DIR = Path("./data")
DATA_DIR.mkdir(parents=True, exist_ok=True)
HITL_PATH = DATA_DIR / "hitl.jsonl"
log = get_logger("hitl.store", "hitl_store.log")


@dataclass
class HitlRecord:
# Explanation: small index item for fast lookups
run_id: str
status: str




class HitlStore:
# Explanation: append-only writes; idempotent on pending
def __init__(self, path: Path = HITL_PATH):
self.path = path
self._index: Dict[str, HitlRecord] = {}
self._load_index()


def _load_index(self) -> None:
if not self.path.exists():
return
with self.path.open("r", encoding="utf-8") as f:
for line in f:
try:
obj = json.loads(line)
if obj.get("type") == "request":
rid = obj["data"]["run_id"]
self._index[rid] = HitlRecord(rid, "pending")
elif obj.get("type") == "decision":
rid = obj["data"]["run_id"]
self._index[rid] = HitlRecord(rid, obj["data"]["decision"])
except Exception as e:
log.error("index_load_error", extra={"error": str(e)})


def write_request(self, req: HitlRequest) -> None:
rec = self._index.get(req.run_id)
if rec and rec.status != "pending":
log.info("request_already_decided", extra={"run_id": req.run_id})
return
payload = {"type": "request", "data": req.model_dump(mode="json")}
self._append(payload)
self._index[req.run_id] = HitlRecord(req.run_id, "pending")
log.info("request_written", extra={"run_id": req.run_id})


def apply_decision(self, dec: HitlDecision) -> None:
payload = {"type": "decision", "data": dec.model_dump(mode="json")}
self._append(payload)
self._index[dec.run_id] = HitlRecord(dec.run_id, dec.decision)
log.info("decision_applied", extra={"run_id": dec.run_id, "decision": dec.decision})


def status(self, run_id: str) -> Optional[str]:
rec = self._index.get(run_id)
return rec.status if rec else None


def _append(self, obj: Dict[str, Any]) -> None:
self.path.parent.mkdir(parents=True, exist_ok=True)
with self.path.open("a", encoding="utf-8") as f:
f.write(json.dumps(obj, ensure_ascii=False) + "\n")