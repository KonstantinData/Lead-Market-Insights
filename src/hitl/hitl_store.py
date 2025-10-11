"""Durable append-only store tracking HITL requests and decisions."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

from .contracts import HitlDecision, HitlRequest
from .logging_setup import get_logger


DATA_DIR = Path("./data")
DATA_DIR.mkdir(parents=True, exist_ok=True)

HITL_PATH = DATA_DIR / "hitl.jsonl"
log = get_logger("hitl.store", "hitl_store.log")


@dataclass(slots=True)
class HitlRecord:
    run_id: str
    status: str


class HitlStore:
    """Append-only persistence layer with an in-memory index."""

    def __init__(self, path: Path = HITL_PATH) -> None:
        self.path = path
        self._index: Dict[str, HitlRecord] = {}
        self._load_index()

    def _load_index(self) -> None:
        if not self.path.exists():
            self._index.clear()
            return

        try:
            index: Dict[str, HitlRecord] = {}
            with self.path.open("r", encoding="utf-8") as handle:
                for line in handle:
                    try:
                        payload = json.loads(line)
                    except json.JSONDecodeError:
                        log.warning("discarding malformed HITL log entry", extra={"line": line})
                        continue

                    data = payload.get("data") or {}
                    run_id = data.get("run_id")
                    if not run_id:
                        continue
                    if payload.get("type") == "request":
                        index[run_id] = HitlRecord(run_id, "pending")
                    elif payload.get("type") == "decision":
                        status = data.get("decision") or "pending"
                        index[run_id] = HitlRecord(run_id, status)
            self._index = index
        except OSError:
            log.exception("failed to load HITL store index")

    def write_request(self, request: HitlRequest) -> None:
        existing = self._index.get(request.run_id)
        if existing and existing.status != "pending":
            log.info("request_already_resolved", extra={"run_id": request.run_id})
            return

        payload = {"type": "request", "data": request.model_dump(mode="json")}
        self._append(payload)
        self._index[request.run_id] = HitlRecord(request.run_id, "pending")
        log.info("request_persisted", extra={"run_id": request.run_id})

    def apply_decision(self, decision: HitlDecision) -> None:
        payload = {"type": "decision", "data": decision.model_dump(mode="json")}
        self._append(payload)
        self._index[decision.run_id] = HitlRecord(decision.run_id, decision.decision)
        log.info(
            "decision_persisted",
            extra={"run_id": decision.run_id, "decision": decision.decision},
        )

    def status(self, run_id: str) -> Optional[str]:
        record = self._index.get(run_id)
        if record is None:
            self._load_index()
            record = self._index.get(run_id)
        return record.status if record else None

    def _append(self, payload: Dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False) + "\n")