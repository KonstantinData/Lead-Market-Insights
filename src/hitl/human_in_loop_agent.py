"""Standalone HITL helper focused on outbound notifications."""

from __future__ import annotations

from typing import Any, Dict, Optional

from .audit_log import AuditLog
from .contracts import AuditEvent, HitlDecision, HitlRequest
from .hitl_store import HitlStore
from .logging_setup import get_logger
from .pii import mask_pii
from .smtp_client import SmtpClient
from .templates import render


log = get_logger("hitl.hia", "hia.log")


class HumanInLoopAgent:
    """Coordinate email based HITL interactions independent of the main app."""

    def __init__(
        self,
        *,
        smtp: Optional[SmtpClient] = None,
        store: Optional[HitlStore] = None,
        audit: Optional[AuditLog] = None,
    ) -> None:
        self.smtp = smtp or SmtpClient()
        self.store = store or HitlStore()
        self.audit = audit or AuditLog()

    def request_approval(
        self,
        run_id: str,
        *,
        to: str,
        subject: str,
        context: Dict[str, Any],
    ) -> str:
        """Send the initial HITL request and persist the pending state."""

        masked = mask_pii(run_id, context)
        body = render("hitl_request_email.j2", {"run_id": run_id, "context": context})
        request = HitlRequest(
            run_id=run_id,
            subject=subject,
            context=context,
            masked_payload=masked,
        )

        message_id = self.smtp.send(to=to, subject=subject, body=body)
        request.msg_id = message_id
        self.store.write_request(request)

        self.audit.append(
            AuditEvent(
                run_id=run_id,
                event="hitl_requested",
                details={"recipient": to, "msg_id": message_id},
            )
        )
        log.info("hitl_requested", extra={"run_id": run_id, "recipient": to})
        return message_id

    def send_reminder(self, run_id: str, *, to: str) -> str:
        """Send a reminder email for an outstanding HITL request."""

        body = render("hitl_reminder_email.j2", {"run_id": run_id})
        message_id = self.smtp.send(to=to, subject="Reminder: HITL pending", body=body)
        self.audit.append(
            AuditEvent(
                run_id=run_id,
                event="hitl_reminder",
                details={"recipient": to, "msg_id": message_id},
            )
        )
        log.info("hitl_reminder", extra={"run_id": run_id, "recipient": to})
        return message_id

    def send_escalation(self, run_id: str, *, to: str) -> str:
        """Escalate a stalled HITL request to an administrator contact."""

        body = render("hitl_escalation_email.j2", {"run_id": run_id})
        message_id = self.smtp.send(
            to=to, subject="Escalation: HITL pending", body=body
        )
        self.audit.append(
            AuditEvent(
                run_id=run_id,
                event="hitl_escalation",
                details={"recipient": to, "msg_id": message_id},
            )
        )
        log.info("hitl_escalation", extra={"run_id": run_id, "recipient": to})
        return message_id

    def record_decision(self, decision: HitlDecision) -> None:
        """Persist an external decision so status lookups work out-of-band."""

        self.store.apply_decision(decision)
        self.audit.append(
            AuditEvent(
                run_id=decision.run_id,
                event="hitl_decision_recorded",
                details={
                    "decision": decision.decision,
                    "actor": decision.actor,
                    "fields": decision.kv,
                },
            )
        )
        log.info(
            "hitl_decision_recorded",
            extra={"run_id": decision.run_id, "decision": decision.decision},
        )
