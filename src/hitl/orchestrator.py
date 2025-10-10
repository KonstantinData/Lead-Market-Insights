"""
Orchestrator: integrate Agents + Audit per sequence diagram.
"""
from __future__ import annotations
from typing import Dict, Any
from .contracts import HitlDecision, AuditEvent
from .parsers import parse_hitl_reply
from .hitl_store import HitlStore
from .audit_log import AuditLog
from .logging_setup import get_logger


log = get_logger("hitl.orch", "orchestrator.log")


class Orchestrator:
# Explanation: route decisions and expose status
def __init__(self):
self.store = HitlStore()
self.audit = AuditLog()


def apply_inbound(self, run_id: str, actor: str, raw_body: str) -> HitlDecision:
dec = parse_hitl_reply(run_id=run_id, actor=actor, body=raw_body)
self.store.apply_decision(dec)
self.audit.append(AuditEvent(run_id=run_id, event=f"hitl_{dec.decision.lower()}", details={"actor": actor}))
log.info("decision_routed", extra={"run_id": run_id, "decision": dec.decision})
return dec


def status(self, run_id: str) -> str | None:
return self.store.status(run_id)