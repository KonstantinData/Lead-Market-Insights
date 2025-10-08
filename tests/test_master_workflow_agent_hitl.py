from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional, Tuple
from types import MethodType

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
        "summary": "Soft trigger meeting for example.ai",
        "organizer": {"email": "organizer@example.com", "displayName": "Org"},
    }
    info = {"company_name": "Example Corp", "web_domain": "example.ai"}

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


async def test_missing_domain_guardrail_requests_info(monkeypatch) -> None:
    backend = DummyBackend({"status": "declined"})
    event = {
        "id": "event-missing-domain",
        "summary": "Soft trigger session without domain",
        "organizer": {"email": "organizer@example.com", "displayName": "Org"},
    }
    extracted = {
        "info": {"company_name": "Example Corp", "web_domain": ""},
        "is_complete": False,
    }

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

    monkeypatch.setenv("HITL_OPERATOR_EMAIL", "ops@example.com")
    monkeypatch.setattr(settings, "hitl_operator_email", None)
    sent_mail: List[Tuple[str, str, str]] = []

    def _fake_send_mail(to: str, subject: str, body: str) -> None:
        sent_mail.append((to, subject, body))

    monkeypatch.setattr("validators.domain_utils.send_mail", _fake_send_mail)

    results = await agent.process_all_events()

    assert results and results[0]["status"] == "hitl_dispatched"
    assert sent_mail, "Missing-domain guardrail should dispatch a HITL email"
    recipient, subject, body = sent_mail[0]
    assert recipient == "ops@example.com"
    assert "Clarify domain" in subject
    assert "event-missing-domain" in body
    assert any(
        err.get("type") == "missing_domain"
        for err in results[0].get("research_errors", [])
    )
    assert backend.requests == [], "Dossier flow should be skipped for placeholder domains"


async def test_audit_log_records_missing_info_flow(tmp_path, monkeypatch) -> None:
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

        monkeypatch.setenv("HITL_OPERATOR_EMAIL", "ops@example.com")
        monkeypatch.setattr(settings, "hitl_operator_email", None)
        sent_mail: List[Tuple[str, str, str]] = []

        def _fake_send_mail(to: str, subject: str, body: str) -> None:
            sent_mail.append((to, subject, body))

        monkeypatch.setattr("validators.domain_utils.send_mail", _fake_send_mail)

        await agent.process_all_events()

        entries = agent.audit_log.load_entries()
        assert len(entries) == 1
        system_entry = entries[0]
        assert system_entry["outcome"] == "hitl_required"
        payload = system_entry.get("payload") or {}
        assert payload.get("reason") == "web_domain missing or invalid; HITL required"
        assert sent_mail, "HITL notification should be emailed"
    finally:
        if agent is not None:
            agent.finalize_run_logs()
        settings.run_log_dir = original_run_dir


async def test_collect_missing_info_pending_sets_status(tmp_path) -> None:
    original_run_dir = settings.run_log_dir
    temp_run_dir = tmp_path / "runs"
    temp_run_dir.mkdir()
    agent: Optional[MasterWorkflowAgent] = None
    try:
        settings.run_log_dir = temp_run_dir
        agent = MasterWorkflowAgent(
            communication_backend=None,
            event_agent=DummyEventAgent([]),
            trigger_agent=DummyTriggerAgent({"trigger": False}),
            extraction_agent=DummyExtractionAgent({"info": {}, "is_complete": False}),
        )

        run_id = generate_run_id()
        current_run_id_var.set(run_id)
        agent.attach_run(run_id, agent.workflow_log_manager)

        def _fake_request_info(self, event_payload, extracted_payload, **_):
            return {
                "status": "pending",
                "audit_id": "audit-123",
                "info": extracted_payload.get("info", {}),
            }

        agent.request_info = MethodType(_fake_request_info, agent)

        event_result: Dict[str, Any] = {}
        follow_up = await agent._collect_missing_info_via_hitl(
            event_result,
            {"id": "event-1"},
            {"info": {"company_name": "", "web_domain": ""}},
            "event-1",
        )

        assert follow_up is None
        assert event_result["status"] == "missing_info_pending"
    finally:
        if agent is not None:
            agent.finalize_run_logs()
        settings.run_log_dir = original_run_dir


async def test_collect_missing_info_incomplete_sets_status(tmp_path) -> None:
    original_run_dir = settings.run_log_dir
    temp_run_dir = tmp_path / "runs"
    temp_run_dir.mkdir()
    agent: Optional[MasterWorkflowAgent] = None
    try:
        settings.run_log_dir = temp_run_dir
        agent = MasterWorkflowAgent(
            communication_backend=None,
            event_agent=DummyEventAgent([]),
            trigger_agent=DummyTriggerAgent({"trigger": False}),
            extraction_agent=DummyExtractionAgent({"info": {}, "is_complete": False}),
        )

        run_id = generate_run_id()
        current_run_id_var.set(run_id)
        agent.attach_run(run_id, agent.workflow_log_manager)

        def _fake_request_info(self, event_payload, extracted_payload, **_):
            return {
                "status": "declined",
                "audit_id": "audit-456",
                "info": {},
            }

        agent.request_info = MethodType(_fake_request_info, agent)

        event_result: Dict[str, Any] = {}
        follow_up = await agent._collect_missing_info_via_hitl(
            event_result,
            {"id": "event-2"},
            {"info": {"company_name": "", "web_domain": ""}},
            "event-2",
        )

        assert follow_up is None
        assert event_result["status"] == "missing_info_incomplete"
    finally:
        if agent is not None:
            agent.finalize_run_logs()
        settings.run_log_dir = original_run_dir


async def test_request_info_records_pending_fields(tmp_path) -> None:
    original_run_dir = settings.run_log_dir
    temp_run_dir = tmp_path / "runs"
    temp_run_dir.mkdir()
    agent: Optional[MasterWorkflowAgent] = None
    try:
        settings.run_log_dir = temp_run_dir
        agent = MasterWorkflowAgent(
            communication_backend=None,
            event_agent=DummyEventAgent([]),
            trigger_agent=DummyTriggerAgent({"trigger": False}),
            extraction_agent=DummyExtractionAgent({"info": {}, "is_complete": False}),
        )

        run_id = generate_run_id()
        current_run_id_var.set(run_id)
        agent.attach_run(run_id, agent.workflow_log_manager)

        pending_calls: List[Dict[str, Any]] = []

        def _capture_pending(request_type: str, audit_id: str, context: Dict[str, Any]) -> None:
            pending_calls.append(
                {
                    "request_type": request_type,
                    "audit_id": audit_id,
                    "context": context,
                }
            )

        agent.on_pending_audit = _capture_pending  # type: ignore[assignment]

        def _fake_human_request_info(
            self,
            event_payload: Dict[str, Any],
            extracted_payload: Dict[str, Any],
        ) -> Dict[str, Any]:
            return {
                "status": "pending",
                "audit_id": "audit-fields",
                "info": {
                    "company_name": "Widget Co",
                    "web_domain": "",
                },
            }

        agent.human_agent.request_info = MethodType(  # type: ignore[assignment]
            _fake_human_request_info, agent.human_agent
        )

        event_payload = {"id": "event-fields", "summary": "Widget briefing"}
        extracted_payload = {"info": {"company_name": "Widget Co"}, "is_complete": False}

        result = agent.request_info(
            event_payload,
            extracted_payload,
            event_id="event-fields",
        )

        assert result["status"] == "pending"
        assert pending_calls and pending_calls[0]["audit_id"] == "audit-fields"
        context = pending_calls[0]["context"]
        assert context["event"]["id"] == "event-fields"
        assert context["requested_fields"] == ["web_domain"]

        pending_calls.clear()

        def _fake_human_request_info_with_fields(
            self,
            event_payload: Dict[str, Any],
            extracted_payload: Dict[str, Any],
        ) -> Dict[str, Any]:
            return {
                "status": "pending",
                "audit_id": "audit-explicit",
                "info": {
                    "company_name": "Widget Co",
                    "web_domain": "",
                },
                "requested_fields": ["company_domain", "web_domain"],
            }

        agent.human_agent.request_info = MethodType(  # type: ignore[assignment]
            _fake_human_request_info_with_fields, agent.human_agent
        )

        second_result = agent.request_info(
            event_payload,
            extracted_payload,
            event_id="event-fields",
        )

        assert second_result["status"] == "pending"
        assert pending_calls and pending_calls[0]["audit_id"] == "audit-explicit"
        explicit_context = pending_calls[0]["context"]
        assert explicit_context["requested_fields"] == [
            "company_domain",
            "web_domain",
        ]
    finally:
        if agent is not None:
            agent.finalize_run_logs()
        settings.run_log_dir = original_run_dir


async def test_continue_after_missing_info_dispatches_when_fields_complete(
    tmp_path,
) -> None:
    original_run_dir = settings.run_log_dir
    temp_run_dir = tmp_path / "runs"
    temp_run_dir.mkdir()
    agent: Optional[MasterWorkflowAgent] = None
    try:
        settings.run_log_dir = temp_run_dir
        agent = MasterWorkflowAgent(
            communication_backend=None,
            event_agent=DummyEventAgent([]),
            trigger_agent=DummyTriggerAgent({"trigger": False}),
            extraction_agent=DummyExtractionAgent({"info": {}, "is_complete": False}),
        )

        run_id = generate_run_id()
        current_run_id_var.set(run_id)
        agent.attach_run(run_id, agent.workflow_log_manager)

        completion_events: List[Any] = []

        def _fake_record_completion(self, event_identifier: Any) -> None:
            completion_events.append(event_identifier)

        agent._record_missing_info_completion = MethodType(  # type: ignore[assignment]
            _fake_record_completion, agent
        )

        dispatched: List[Dict[str, Any]] = []

        async def _fake_process_dispatch(
            self,
            event_payload: Dict[str, Any],
            info_payload: Dict[str, Any],
            event_result_payload: Dict[str, Any],
            event_identifier: Optional[Any],
            *,
            force_internal: bool,
            internal_result: Optional[Dict[str, Any]] = None,
            requires_dossier_override: Optional[bool] = None,
        ) -> None:
            dispatched.append(
                {
                    "event": event_payload,
                    "info": dict(info_payload),
                    "event_result": dict(event_result_payload),
                    "event_id": event_identifier,
                    "force_internal": force_internal,
                }
            )
            event_result_payload["status"] = "crm_dispatched"

        agent._process_crm_dispatch = MethodType(  # type: ignore[assignment]
            _fake_process_dispatch, agent
        )

        context = {
            "event": {
                "id": "event-complete",
                "summary": "Review plans for acme-industries.com",
            },
            "info": {"company_name": "Acme Industries"},
            "event_id": "event-complete",
        }

        result = await agent.continue_after_missing_info(
            "audit-complete",
            {"company_domain": "Acme-Industries.COM"},
            context,
        )

        assert result is not None
        assert result["status"] == "crm_dispatched"
        assert completion_events == ["event-complete"]
        assert dispatched and dispatched[0]["force_internal"] is True
        assert dispatched[0]["info"].get("company_domain") == "acme-industries.com"
    finally:
        if agent is not None:
            agent.finalize_run_logs()
        settings.run_log_dir = original_run_dir


async def test_continue_after_missing_info_requests_followup_completion(
    tmp_path,
) -> None:
    original_run_dir = settings.run_log_dir
    temp_run_dir = tmp_path / "runs"
    temp_run_dir.mkdir()
    agent: Optional[MasterWorkflowAgent] = None
    try:
        settings.run_log_dir = temp_run_dir
        agent = MasterWorkflowAgent(
            communication_backend=None,
            event_agent=DummyEventAgent([]),
            trigger_agent=DummyTriggerAgent({"trigger": False}),
            extraction_agent=DummyExtractionAgent({"info": {}, "is_complete": False}),
        )

        run_id = generate_run_id()
        current_run_id_var.set(run_id)
        agent.attach_run(run_id, agent.workflow_log_manager)

        completion_events: List[Any] = []

        def _fake_record_completion(self, event_identifier: Any) -> None:
            completion_events.append(event_identifier)

        agent._record_missing_info_completion = MethodType(  # type: ignore[assignment]
            _fake_record_completion, agent
        )

        dispatched: List[Dict[str, Any]] = []

        async def _fake_process_dispatch(
            self,
            event_payload: Dict[str, Any],
            info_payload: Dict[str, Any],
            event_result_payload: Dict[str, Any],
            event_identifier: Optional[Any],
            *,
            force_internal: bool,
            internal_result: Optional[Dict[str, Any]] = None,
            requires_dossier_override: Optional[bool] = None,
        ) -> None:
            dispatched.append(
                {
                    "event": event_payload,
                    "info": dict(info_payload),
                    "event_result": dict(event_result_payload),
                    "event_id": event_identifier,
                    "force_internal": force_internal,
                }
            )
            event_result_payload["status"] = "crm_dispatched"

        agent._process_crm_dispatch = MethodType(  # type: ignore[assignment]
            _fake_process_dispatch, agent
        )

        request_calls: List[Dict[str, Any]] = []

        def _fake_request_info(
            self,
            event_payload: Dict[str, Any],
            extracted_payload: Dict[str, Any],
            *,
            event_id: Optional[Any] = None,
        ) -> Dict[str, Any]:
            request_calls.append(
                {"event": event_payload, "extracted": extracted_payload, "event_id": event_id}
            )
            return {
                "is_complete": True,
                "info": {
                    "company_name": "Widget Co",
                    "company_domain": "widgetco.org",
                },
            }

        agent.request_info = MethodType(_fake_request_info, agent)  # type: ignore[assignment]

        context = {
            "event": {
                "id": "event-followup",
                "summary": "Strategy sync for widgetco.org",
            },
            "info": {"company_name": "Widget Co"},
            "event_id": "event-followup",
        }

        result = await agent.continue_after_missing_info(
            "audit-followup",
            {},
            context,
        )

        assert request_calls and request_calls[0]["event_id"] == "event-followup"
        assert result is not None
        assert result["status"] == "crm_dispatched"
        assert completion_events == ["event-followup"]
        assert dispatched and dispatched[0]["info"].get("company_domain") == "widgetco.org"
    finally:
        if agent is not None:
            agent.finalize_run_logs()
        settings.run_log_dir = original_run_dir


async def test_collect_missing_info_preserves_hitl_domain(tmp_path) -> None:
    original_run_dir = settings.run_log_dir
    temp_run_dir = tmp_path / "runs"
    temp_run_dir.mkdir()
    agent: Optional[MasterWorkflowAgent] = None
    try:
        settings.run_log_dir = temp_run_dir
        agent = MasterWorkflowAgent(
            communication_backend=None,
            event_agent=DummyEventAgent([]),
            trigger_agent=DummyTriggerAgent({"trigger": False}),
            extraction_agent=DummyExtractionAgent({"info": {}, "is_complete": False}),
        )

        run_id = generate_run_id()
        current_run_id_var.set(run_id)
        agent.attach_run(run_id, agent.workflow_log_manager)

        completion_events: List[Any] = []

        def _fake_record_completion(self, event_identifier: Any) -> None:
            completion_events.append(event_identifier)

        agent._record_missing_info_completion = MethodType(  # type: ignore[assignment]
            _fake_record_completion, agent
        )

        def _fake_request_info(
            self,
            event_payload: Dict[str, Any],
            extracted_payload: Dict[str, Any],
            *,
            event_id: Optional[Any] = None,
        ) -> Dict[str, Any]:
            return {
                "audit_id": "audit-domain",
                "is_complete": True,
                "info": {
                    "company_name": "Example Corp",
                    "web_domain": "ExampleCorp.TEST",
                },
            }

        agent.request_info = MethodType(_fake_request_info, agent)  # type: ignore[assignment]

        event_result: Dict[str, Any] = {}
        follow_up = await agent._collect_missing_info_via_hitl(
            event_result,
            {"id": "event-domain", "summary": "Quarterly sync"},
            {"info": {"company_name": "Example Corp"}, "is_complete": False},
            "event-domain",
        )

        assert completion_events == ["event-domain"]
        assert event_result["status"] == "missing_info_completed"
        assert follow_up is not None
        assert follow_up["audit_id"] == "audit-domain"
        assert follow_up["info"]["company_domain"] == "examplecorp.test"
        assert follow_up["info"]["web_domain"] == "examplecorp.test"
        assert follow_up["domain_meta"]["source"] == "hitl_provided"
    finally:
        if agent is not None:
            agent.finalize_run_logs()
        settings.run_log_dir = original_run_dir
