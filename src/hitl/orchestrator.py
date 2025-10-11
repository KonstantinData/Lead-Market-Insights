"""Standalone coordinator for inbox-driven HITL decisions."""

from __future__ import annotations

from typing import Optional

from .audit_log import AuditLog
from .contracts import AuditEvent, HitlDecision
from .hitl_store import HitlStore
from .logging_setup import get_logger
from .parsers import parse_hitl_reply


log = get_logger("hitl.orch", "orchestrator.log")


class Orchestrator:
    """Normalise inbound replies and persist their outcome."""

    def __init__(
        self,
        *,
        store: Optional[HitlStore] = None,
        audit: Optional[AuditLog] = None,
    ) -> None:
        self.store = store or HitlStore()
        self.audit = audit or AuditLog()

    def apply_inbound(self, run_id: str, *, actor: str, raw_body: str) -> HitlDecision:
        """Parse *raw_body*, persist the decision and return the structured model."""

        decision = parse_hitl_reply(run_id=run_id, actor=actor, body=raw_body)
        self.store.apply_decision(decision)
        self.audit.append(
            AuditEvent(
                run_id=run_id,
                event="hitl_decision",
                details={"actor": actor, "decision": decision.decision},
            )
        )
        log.info(
            "hitl_decision_processed",
            extra={"run_id": run_id, "decision": decision.decision},
        )
        return decision

    def status(self, run_id: str) -> Optional[str]:
        """Return the last known status for *run_id* if present."""

        return self.store.status(run_id)
