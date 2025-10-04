from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional

import pytest

from agents.master_workflow_agent import MasterWorkflowAgent
from config.config import settings
from utils.observability import current_run_id_var, generate_run_id


pytestmark = pytest.mark.asyncio


class DummyBackend:
    def __init__(self, response: Dict[str, Any]):
        self.response = response
        self.requests: List[Dict[str, Any]] = []

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
        return self.response


class DummyEventAgent:
    def __init__(self, events: Iterable[Dict[str, Any]]):
        self._events = list(events)

    async def poll(self) -> Iterable[Dict[str, Any]]:
        return list(self._events)


class DummyTriggerAgent:
    def __init__(self, result: Dict[str, Any]):
        self._result = result

    async def check(self, _event: Dict[str, Any]) -> Dict[str, Any]:
        return self._result


class DummyExtractionAgent:
    def __init__(self, response: Dict[str, Any]):
        self._response = response

    async def extract(self, _event: Dict[str, Any]) -> Dict[str, Any]:
        return self._response


def _prepare_agent(backend: Optional[DummyBackend]) -> MasterWorkflowAgent:
    event = {
        "id": "event-123",
        "summary": "Soft trigger meeting",
        "organizer": {"email": "organizer@example.com", "displayName": "Org"},
    }
    info = {"company_name": "Example Corp", "web_domain": "example.com"}

    agent = MasterWorkflowAgent(
        communication_backend=backend,
        event_agent=DummyEventAgent([event]),
        trigger_agent=DummyTriggerAgent(
            {
                "trigger": True,
                "type": "soft",
                "matched_word": "briefing",
                "matched_field": "summary",
            }
        ),
        extraction_agent=DummyExtractionAgent({"info": info, "is_complete": True}),
    )
    agent._send_calls: List[Dict[str, Any]] = []

    async def _capture_send(
        to_event: Dict[str, Any], event_info: Dict[str, Any]
    ) -> None:
        agent._send_calls.append({"event": to_event, "info": event_info})

    agent._send_to_crm_agent = _capture_send  # type: ignore[assignment]
    run_id = generate_run_id()
    current_run_id_var.set(run_id)
    agent.attach_run(run_id, agent.workflow_log_manager)
    return agent


async def test_soft_trigger_dossier_request_accepted() -> None:
    backend = DummyBackend(
        {"dossier_required": True, "details": {"note": "Yes, please prepare it."}}
    )
    agent = _prepare_agent(backend)

    await agent.process_all_events()

    assert len(agent._send_calls) == 1
    assert agent._send_calls[0]["info"]["company_name"] == "Example Corp"

    assert backend.requests, "Backend should have been invoked"
    first_request = backend.requests[0]
    assert first_request["contact"]["email"] == "organizer@example.com"
    assert "Soft trigger meeting" in first_request["subject"]


async def test_soft_trigger_dossier_request_declined() -> None:
    backend = DummyBackend(
        {"dossier_required": False, "details": {"note": "No dossier required."}}
    )
    agent = _prepare_agent(backend)

    await agent.process_all_events()

    assert agent._send_calls == []
    assert len(backend.requests) == 1
    assert backend.requests[0]["info"]["company_name"] == "Example Corp"


async def test_soft_trigger_dossier_request_declined_status_only() -> None:
    backend = DummyBackend({"status": "declined"})
    agent = _prepare_agent(backend)

    await agent.process_all_events()

    assert agent._send_calls == []
    assert len(backend.requests) == 1


async def test_soft_trigger_dossier_request_missing_backend_skips() -> None:
    agent = _prepare_agent(None)

    results = await agent.process_all_events()

    assert len(results) == 1
    outcome = results[0]
    assert outcome["status"] == "dossier_backend_unavailable"
    assert outcome["hitl_dossier"]["status"] == "skipped"
    assert outcome["hitl_dossier"]["dossier_required"] is None
    assert agent._send_calls == []


async def test_audit_log_records_dossier_acceptance(tmp_path) -> None:
    backend = DummyBackend(
        {"dossier_required": True, "details": {"note": "Yes, please prepare it."}}
    )
    original_run_dir = settings.run_log_dir
    temp_run_dir = tmp_path / "runs"
    temp_run_dir.mkdir()
    agent: Optional[MasterWorkflowAgent] = None
    try:
        settings.run_log_dir = temp_run_dir
        agent = _prepare_agent(backend)

        await agent.process_all_events()

        entries = agent.audit_log.load_entries()
        assert len(entries) == 2
        assert {entry["stage"] for entry in entries} == {"request", "response"}
        assert len({entry["audit_id"] for entry in entries}) == 1
        response_entry = next(
            entry for entry in entries if entry["stage"] == "response"
        )
        assert response_entry["outcome"] == "approved"
        assert response_entry["request_type"] == "dossier_confirmation"
        assert response_entry["responder"] == "DummyBackend"

        log_contents = agent.log_file_path.read_text(encoding="utf-8")
        assert response_entry["audit_id"] in log_contents
        assert "[audit_id=n/a]" not in log_contents
    finally:
        if agent is not None:
            agent.finalize_run_logs()
        settings.run_log_dir = original_run_dir


async def test_audit_log_records_dossier_decline(tmp_path) -> None:
    backend = DummyBackend(
        {"dossier_required": False, "details": {"note": "No dossier required."}}
    )
    original_run_dir = settings.run_log_dir
    temp_run_dir = tmp_path / "runs"
    temp_run_dir.mkdir()
    agent: Optional[MasterWorkflowAgent] = None
    try:
        settings.run_log_dir = temp_run_dir
        agent = _prepare_agent(backend)

        await agent.process_all_events()

        entries = agent.audit_log.load_entries()
        assert len(entries) == 2
        assert {entry["stage"] for entry in entries} == {"request", "response"}
        response_entry = next(
            entry for entry in entries if entry["stage"] == "response"
        )
        assert response_entry["outcome"] == "declined"

        log_contents = agent.log_file_path.read_text(encoding="utf-8")
        assert response_entry["audit_id"] in log_contents
        assert "[audit_id=n/a]" not in log_contents
    finally:
        if agent is not None:
            agent.finalize_run_logs()
        settings.run_log_dir = original_run_dir


async def test_soft_trigger_dossier_request_pending(tmp_path) -> None:
    backend = DummyBackend({"status": "pending", "details": {"note": "Awaiting team"}})
    original_run_dir = settings.run_log_dir
    original_workflow_dir = settings.workflow_log_dir
    temp_run_dir = tmp_path / "runs"
    temp_workflow_dir = tmp_path / "workflows"
    temp_run_dir.mkdir()
    temp_workflow_dir.mkdir()
    agent: Optional[MasterWorkflowAgent] = None
    try:
        settings.run_log_dir = temp_run_dir
        settings.workflow_log_dir = temp_workflow_dir
        agent = _prepare_agent(backend)

        await agent.process_all_events()

        assert agent._send_calls == []
        assert backend.requests, "Pending backend should receive request"

        log_contents = agent.log_file_path.read_text(encoding="utf-8")
        assert "decision pending" in log_contents

        workflow_files = list(temp_workflow_dir.glob("*.jsonl"))
        assert workflow_files, "Workflow reminder logs should be recorded"
        workflow_log_text = workflow_files[0].read_text(encoding="utf-8")
        assert "hitl_dossier_pending" in workflow_log_text
    finally:
        if agent is not None:
            agent.finalize_run_logs()
        settings.run_log_dir = original_run_dir
        settings.workflow_log_dir = original_workflow_dir


async def test_soft_trigger_dossier_request_approved_status_only() -> None:
    backend = DummyBackend({"status": "approved"})
    agent = _prepare_agent(backend)

    await agent.process_all_events()

    assert len(agent._send_calls) == 1
    assert len(backend.requests) == 1


async def test_audit_log_records_missing_info_flow(tmp_path) -> None:
    original_run_dir = settings.run_log_dir
    temp_run_dir = tmp_path / "runs"
    temp_run_dir.mkdir()
    agent: Optional[MasterWorkflowAgent] = None
    try:
        settings.run_log_dir = temp_run_dir
        event = {
            "id": "event-hard-1",
            "summary": "Hard trigger missing info",
            "organizer": {
                "email": "organizer@example.com",
                "displayName": "Org",
            },
        }
        extracted = {
            "info": {"company_name": None, "web_domain": ""},
            "is_complete": False,
        }
        agent = MasterWorkflowAgent(
            communication_backend=None,
            event_agent=DummyEventAgent([event]),
            trigger_agent=DummyTriggerAgent(
                {
                    "trigger": True,
                    "type": "hard",
                    "matched_word": "briefing",
                    "matched_field": "summary",
                }
            ),
            extraction_agent=DummyExtractionAgent(extracted),
        )
        agent._send_calls = []  # type: ignore[attr-defined]

        async def _capture_send(
            to_event: Dict[str, Any], event_info: Dict[str, Any]
        ) -> None:
            agent._send_calls.append({"event": to_event, "info": event_info})

        agent._send_to_crm_agent = _capture_send  # type: ignore[assignment]

        run_id = generate_run_id()
        current_run_id_var.set(run_id)
        agent.attach_run(run_id, agent.workflow_log_manager)

        await agent.process_all_events()

        entries = agent.audit_log.load_entries()
        assert len(entries) == 2
        assert {entry["request_type"] for entry in entries} == {"missing_info"}
        response_entry = next(
            entry for entry in entries if entry["stage"] == "response"
        )
        assert response_entry["outcome"] == "completed"
        assert response_entry["responder"] == "simulation"

        log_contents = agent.log_file_path.read_text(encoding="utf-8")
        assert response_entry["audit_id"] in log_contents
        assert "[audit_id=n/a]" not in log_contents
    finally:
        if agent is not None:
            agent.finalize_run_logs()
        settings.run_log_dir = original_run_dir
