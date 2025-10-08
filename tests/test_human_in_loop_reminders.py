import asyncio
import json
from datetime import timedelta
from pathlib import Path
from typing import Any, Dict
from types import SimpleNamespace

import pytest

from agents.human_in_loop_agent import (
    DossierConfirmationBackendUnavailable,
    HumanInLoopAgent,
)
from logs.workflow_log_manager import WorkflowLogManager


def build_settings(tmp_path) -> SimpleNamespace:
    workflow_dir = tmp_path / "workflows"
    workflow_dir.mkdir(parents=True, exist_ok=True)
    log_storage_dir = tmp_path / "logs"
    log_storage_dir.mkdir(parents=True, exist_ok=True)
    reminder_dir = log_storage_dir / "reminders"
    reminder_dir.mkdir(parents=True, exist_ok=True)

    admin_email = "ops@example.com"
    escalation_email = "lead@example.com"

    settings = SimpleNamespace(
        workflow_log_dir=str(workflow_dir),
        log_storage_dir=log_storage_dir,
        hitl_admin_email=admin_email,
        hitl_admin_reminder_hours=(24.0,),
        hitl_reminder_delay_hours=0.0,
        hitl_max_retries=2,
        hitl_escalation_email=escalation_email,
        hitl_reminder_log_dir=reminder_dir,
    )

    settings.hitl = SimpleNamespace(
        operator_email=admin_email,
        admin_email=admin_email,
        workflow_log_dir=str(workflow_dir),
        escalation_email=escalation_email,
        reminder_delay_hours=0.0,
        max_retries=2,
        reminder_log_dir=str(reminder_dir),
    )

    return settings


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
        self.sent_emails.append(
            {"recipient": recipient, "subject": subject, "body": body}
        )
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
    settings = build_settings(tmp_path)
    agent = HumanInLoopAgent(
        communication_backend=backend,
        reminder_policy=policy,
        settings_override=settings,
    )

    workflow_dir = Path(settings.workflow_log_dir)
    run_directory = workflow_dir / "run-123"
    run_directory.mkdir(parents=True, exist_ok=True)
    agent.set_run_context(
        "run-123", WorkflowLogManager(workflow_dir), run_directory=run_directory
    )

    event = {
        "id": "evt-1",
        "summary": "Pending dossier",
        "organizer": {"email": "organizer@example.com", "displayName": "Org"},
    }
    info = {"company_name": "Example Corp", "web_domain": "example.ai"}

    response = agent.request_dossier_confirmation(event, info)
    assert response["status"] == "pending"

    await asyncio.sleep(0.4)

    assert backend.sent_emails, "Reminders should trigger email sends"
    assert backend.sent_emails[0]["subject"].startswith("Reminder:")
    assert any(
        email["subject"].startswith("Escalation:") for email in backend.sent_emails
    )

    workflow_files = list(workflow_dir.glob("*.jsonl"))
    assert workflow_files, "Workflow logs should record reminders"
    workflow_text = workflow_files[0].read_text(encoding="utf-8")
    assert "hitl_dossier_pending" in workflow_text
    assert "hitl_dossier_reminder_scheduled" in workflow_text

    reminder_file = Path(settings.hitl_reminder_log_dir) / "run-123.jsonl"
    assert reminder_file.exists(), "Reminder JSONL should be persisted"
    reminder_entries = [json.loads(line) for line in reminder_file.read_text().splitlines()]
    assert any(entry["step"] == "reminder_sent" for entry in reminder_entries)

    reminder_artifact = run_directory / "reminder.json"
    assert reminder_artifact.exists(), "Run-level reminder artifact should be created"
    reminder_payload = json.loads(reminder_artifact.read_text())
    assert reminder_payload["run_id"] == "run-123"
    assert reminder_payload["entries"], "Reminder artifact should record entries"
    escalation_artifact = run_directory / "escalation.json"
    assert escalation_artifact.exists(), "Escalation artifact should be created"
    escalation_payload = json.loads(escalation_artifact.read_text())
    assert escalation_payload["entries"], "Escalation artifact should record entries"

    agent.shutdown()


def test_dossier_confirmation_without_backend_raises() -> None:
    agent = HumanInLoopAgent(communication_backend=None)
    event = {
        "id": "evt-2",
        "summary": "No backend",
        "organizer": {"email": "organizer@example.com"},
    }
    info = {"company_name": "Example Corp"}

    with pytest.raises(DossierConfirmationBackendUnavailable):
        agent.request_dossier_confirmation(event, info)
