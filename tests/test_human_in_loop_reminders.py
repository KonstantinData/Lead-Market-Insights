import asyncio
from datetime import timedelta
from typing import Any, Dict

import pytest

from agents.human_in_loop_agent import HumanInLoopAgent
from logs.workflow_log_manager import WorkflowLogManager


class FakeBackend:
    def __init__(self) -> None:
        self.sent_emails: list[Dict[str, Any]] = []
        self.requests: list[Dict[str, Any]] = []

    def request_confirmation(
        self,
        contact: Dict[str, Any],
        subject: str,
        message: str,
        event: Dict[str, Any],
        info: Dict[str, Any],
        payload: Dict[str, Any],
    ) -> Dict[str, Any]:
        self.requests.append(
            {
                "contact": contact,
                "subject": subject,
                "message": message,
                "event": event,
                "info": info,
                "payload": payload,
            }
        )
        return {"status": "pending", "details": {"note": "Awaiting organizer"}}

    async def send_email_async(
        self, recipient: str, subject: str, body: str, **_: Any
    ) -> bool:
        self.sent_emails.append({"recipient": recipient, "subject": subject, "body": body})
        return True


@pytest.mark.asyncio
async def test_pending_confirmation_triggers_reminders(tmp_path) -> None:
    backend = FakeBackend()
    policy = HumanInLoopAgent.DossierReminderPolicy(
        initial_delay=timedelta(seconds=0),
        follow_up_delays=(timedelta(seconds=0),),
        escalation_delay=timedelta(seconds=0),
        escalation_recipient="ops@example.com",
    )
    agent = HumanInLoopAgent(communication_backend=backend, reminder_policy=policy)

    workflow_dir = tmp_path / "workflow"
    workflow_dir.mkdir()
    agent.set_run_context("run-123", WorkflowLogManager(workflow_dir))

    event = {
        "id": "evt-1",
        "summary": "Pending dossier",
        "organizer": {"email": "organizer@example.com", "displayName": "Org"},
    }
    info = {"company_name": "Example Corp", "web_domain": "example.com"}

    response = agent.request_dossier_confirmation(event, info)
    assert response["status"] == "pending"

    await asyncio.sleep(0.4)

    assert backend.sent_emails, "Reminders should trigger email sends"
    assert backend.sent_emails[0]["subject"].startswith("Reminder:")
    assert any(email["subject"].startswith("Escalation:") for email in backend.sent_emails)

    workflow_files = list(workflow_dir.glob("*.jsonl"))
    assert workflow_files, "Workflow logs should record reminders"
    workflow_text = workflow_files[0].read_text(encoding="utf-8")
    assert "hitl_dossier_pending" in workflow_text
    assert "hitl_dossier_reminder_scheduled" in workflow_text

    agent.shutdown()
