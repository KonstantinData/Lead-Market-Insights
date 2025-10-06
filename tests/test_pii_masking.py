from __future__ import annotations
from __future__ import annotations

from typing import Any, Dict, Iterable

import pytest

from agents.master_workflow_agent import MasterWorkflowAgent
from config.config import settings
from utils.observability import current_run_id_var, generate_run_id
from utils.pii import mask_pii


class DummyEventAgent:
    def __init__(self, events: Iterable[Dict[str, Any]]):
        self._events = list(events)

    async def poll(self) -> Iterable[Dict[str, Any]]:
        return list(self._events)


class DummyTriggerAgent:
    def __init__(self, trigger_type: str = "hard") -> None:
        self._trigger_type = trigger_type

    async def check(self, _event: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "trigger": True,
            "type": self._trigger_type,
            "matched_word": "demo",
            "matched_field": "summary",
        }


class DummyExtractionAgent:
    async def extract(self, event: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "info": {"company_name": "Example", "contact_name": "Ada"},
            "is_complete": True,
        }


class DummyHumanBackend:
    def __init__(self) -> None:
        self.requests = []

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
        return {"dossier_required": True, "details": {"accepted": True}}


def test_mask_pii_respects_whitelist():
    payload = {
        "organizer": {"email": "user@example.com", "name": "Alice"},
        "info": {"company_name": "Example", "contact_name": "Bob"},
    }
    masked = mask_pii(payload, whitelist={"company_name"})

    assert masked["organizer"]["email"] == "<redacted-email>"
    assert masked["organizer"]["name"] == "<redacted-name>"
    assert masked["info"]["company_name"] == "Example"
    assert masked["info"]["contact_name"] == "<redacted-name>"


@pytest.mark.asyncio
async def test_master_agent_masks_logged_events(orchestrator_environment):
    original_run_dir = settings.run_log_dir
    original_mask_logs = settings.mask_pii_in_logs
    original_whitelist = set(settings.pii_field_whitelist)
    original_compliance = settings.compliance_mode
    agent: MasterWorkflowAgent | None = None

    try:
        settings.mask_pii_in_logs = True
        settings.pii_field_whitelist = original_whitelist
        settings.compliance_mode = "strict"
        run_dir = orchestrator_environment["run_dir"]
        run_dir.mkdir(exist_ok=True)
        settings.run_log_dir = run_dir

        event = {
            "id": "evt-001",
            "summary": "Launch",
            "organizer": {"email": "organizer@example.com", "displayName": "Owner"},
        }

        agent = MasterWorkflowAgent(
            communication_backend=None,
            event_agent=DummyEventAgent([event]),
            trigger_agent=DummyTriggerAgent(),
            extraction_agent=DummyExtractionAgent(),
        )

        run_id = generate_run_id()
        current_run_id_var.set(run_id)
        agent.attach_run(run_id, agent.workflow_log_manager)

        await agent.process_all_events()

        log_text = agent.log_file_path.read_text(encoding="utf-8")
        assert "organizer@example.com" not in log_text
        assert "<redacted-email>" in log_text
    finally:
        if agent is not None:
            agent.finalize_run_logs()
        settings.run_log_dir = original_run_dir
        settings.mask_pii_in_logs = original_mask_logs
        settings.pii_field_whitelist = original_whitelist
        settings.compliance_mode = original_compliance


@pytest.mark.asyncio
async def test_human_agent_masks_messages(orchestrator_environment):
    backend = DummyHumanBackend()
    original_mask_messages = settings.mask_pii_in_messages
    original_run_dir = settings.run_log_dir
    original_whitelist = set(settings.pii_field_whitelist)
    original_compliance = settings.compliance_mode
    agent: MasterWorkflowAgent | None = None

    try:
        settings.mask_pii_in_messages = True
        settings.pii_field_whitelist = original_whitelist
        settings.compliance_mode = "strict"
        run_dir = orchestrator_environment["run_dir"]
        run_dir.mkdir(exist_ok=True)
        settings.run_log_dir = run_dir

        agent = MasterWorkflowAgent(
            communication_backend=backend,
            event_agent=DummyEventAgent(
                [
                    {
                        "id": "evt-002",
                        "summary": "Demo with user@example.com",
                        "organizer": {
                            "email": "organizer@example.com",
                            "displayName": "Owner",
                        },
                    }
                ]
            ),
            trigger_agent=DummyTriggerAgent("soft"),
            extraction_agent=DummyExtractionAgent(),
        )

        run_id = generate_run_id()
        current_run_id_var.set(run_id)
        agent.attach_run(run_id, agent.workflow_log_manager)

        await agent.process_all_events()

        assert backend.requests, "Backend should receive a request"
        message = backend.requests[0]["message"]
        assert "<redacted-name>" in message
        assert "organizer@example.com" not in message
    finally:
        if agent is not None:
            agent.finalize_run_logs()
        settings.mask_pii_in_messages = original_mask_messages
        settings.run_log_dir = original_run_dir
        settings.pii_field_whitelist = original_whitelist
        settings.compliance_mode = original_compliance
