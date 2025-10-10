"""
HIA: render → mask → write pending → send → reminders/escalation.
"""
from __future__ import annotations
from typing import Dict, Any
from .contracts import HitlRequest, HitlDecision, AuditEvent
from .templates import render
from .pii import mask_pii
from .smtp_client import SmtpClient
from .hitl_store import HitlStore
from .audit_log import AuditLog
from .logging_setup import get_logger


log = get_logger("hitl.hia", "hia.log")


class HumanInLoopAgent:
# Explanation: orchestration of HITL email lifecycle
def __init__(self, smtp: SmtpClient | None = None):
self.smtp = smtp or SmtpClient()
self.store = HitlStore()
self.audit = AuditLog()


def request_approval(self, run_id: str, to: str, subject: str, context: Dict[str, Any]) -> str:
masked = mask_pii(run_id, context)
body = render("hitl_request_email.j2", {"run_id": run_id, "context": context})
req = HitlRequest(run_id=run_id, subject=subject, context=context, masked_payload=masked)
self.store.write_request(req)
msg_id = self.smtp.send(to=to, subject=subject, body=body)
self.audit.append(AuditEvent(run_id=run_id, event="hitl_requested", details={"msg_id": msg_id}))
log.info("hitl_requested", extra={"run_id": run_id, "to": to})
return msg_id


def send_reminder(self, run_id: str, to: str) -> str:
body = render("hitl_reminder_email.j2", {"run_id": run_id})
mid = self.smtp.send(to=to, subject="Reminder: HITL pending", body=body)
self.audit.append(AuditEvent(run_id=run_id, event="hitl_reminder", details={"msg_id": mid}))
return mid


def send_escalation(self, run_id: str, admin_to: str) -> str:
body = render("hitl_escalation_email.j2", {"run_id": run_id})
mid = self.smtp.send(to=admin_to, subject="Escalation: HITL pending", body=body)
self.audit.append(AuditEvent(run_id=run_id, event="hitl_escalation", details={"msg_id": mid}))
return mid