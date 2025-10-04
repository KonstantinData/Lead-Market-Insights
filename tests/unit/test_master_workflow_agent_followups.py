import contextlib
from typing import Any, Dict, Optional

import pytest
from unittest.mock import AsyncMock

from agents.master_workflow_agent import MasterWorkflowAgent


class DummyHumanAgent:
    def __init__(self, follow_up: Optional[Dict[str, Any]] = None) -> None:
        self.follow_up = follow_up or {}
        self.requests: list[Dict[str, Any]] = []

    def request_info(self, event: Dict[str, Any], extracted: Dict[str, Any]) -> Dict[str, Any]:
        self.requests.append({"event": event, "extracted": extracted})
        return dict(self.follow_up)

    def request_dossier_confirmation(
        self, event: Dict[str, Any], info: Dict[str, Any]
    ) -> Dict[str, Any]:  # pragma: no cover - not used in these tests
        raise NotImplementedError


@pytest.fixture(autouse=True)
def _patch_observability(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "agents.master_workflow_agent.observe_operation",
        lambda *args, **kwargs: contextlib.nullcontext(),
    )
    monkeypatch.setattr(
        "agents.master_workflow_agent.record_hitl_outcome",
        lambda *args, **kwargs: None,
    )


@pytest.fixture(autouse=True)
def _patch_workflow_step_recorder(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[str, Optional[str], str]] = []

    class _Recorder:
        def record_step(
            self, run_id: str, event_id: Optional[str], step: str, *, extra: Any = None
        ) -> bool:
            calls.append((run_id, event_id, step))
            return True

        def should_write_manifest(self, run_id: str) -> bool:  # pragma: no cover - unused
            return True

        def clear_run(self, run_id: str) -> None:  # pragma: no cover - unused
            pass

    recorder = _Recorder()
    monkeypatch.setattr("agents.master_workflow_agent.workflow_step_recorder", recorder)
    monkeypatch.setattr("agents.workflow_orchestrator.workflow_step_recorder", recorder)


def _build_agent(human_agent: DummyHumanAgent) -> MasterWorkflowAgent:
    agent = MasterWorkflowAgent.__new__(MasterWorkflowAgent)
    agent.run_id = "run-123"
    agent.human_agent = human_agent
    agent.on_pending_audit = None
    agent._process_crm_dispatch = AsyncMock()
    return agent


@pytest.mark.asyncio
async def test_missing_info_continuation_dispatches_when_complete(monkeypatch: pytest.MonkeyPatch) -> None:
    human = DummyHumanAgent()
    agent = _build_agent(human)
    dispatch_calls: list[Dict[str, Any]] = []

    async def _fake_dispatch(
        event: Dict[str, Any],
        info: Dict[str, Any],
        result: Dict[str, Any],
        event_id: str,
        *,
        force_internal: bool,
    ) -> None:
        dispatch_calls.append(
            {
                "event": event,
                "info": info,
                "result": result,
                "event_id": event_id,
                "force_internal": force_internal,
            }
        )

    monkeypatch.setattr(agent, "_process_crm_dispatch", _fake_dispatch)
    monkeypatch.setattr(agent, "_record_missing_info_completion", lambda event_id: None)

    context = {
        "event": {"id": "evt-1"},
        "info": {"company_name": "Acme"},
        "event_id": "evt-1",
    }

    result = await agent.continue_after_missing_info(
        "audit-1", {"company_domain": "acme.com"}, context
    )

    assert result is not None
    assert result["status"] == "missing_info_followup"
    assert dispatch_calls and dispatch_calls[0]["force_internal"] is True
    assert dispatch_calls[0]["info"]["company_domain"] == "acme.com"


@pytest.mark.asyncio
async def test_missing_info_continuation_registers_pending(monkeypatch: pytest.MonkeyPatch) -> None:
    follow_up = {
        "status": "pending",
        "audit_id": "audit-2",
        "info": {"company_name": "Acme", "company_domain": ""},
    }
    human = DummyHumanAgent(follow_up)
    agent = _build_agent(human)
    pending_calls: list[tuple[str, str, Dict[str, Any]]] = []

    def _on_pending(kind: str, audit_id: str, context: Dict[str, Any]) -> None:
        pending_calls.append((kind, audit_id, context))

    agent.on_pending_audit = _on_pending
    monkeypatch.setattr(agent, "_process_crm_dispatch", lambda *args, **kwargs: None)

    context = {
        "event": {"id": "evt-2"},
        "info": {"company_name": "Acme"},
        "event_id": "evt-2",
    }

    result = await agent.continue_after_missing_info("audit-1", {}, context)

    assert result is None
    assert len(human.requests) == 1
    assert pending_calls and pending_calls[0][0] == "missing_info"
    assert pending_calls[0][1] == "audit-2"
    context_payload = pending_calls[0][2]
    assert context_payload["run_id"] == agent.run_id
    assert context_payload["requested_fields"] == ["company_domain"]


@pytest.mark.asyncio
async def test_missing_info_follow_up_completes(monkeypatch: pytest.MonkeyPatch) -> None:
    follow_up = {
        "status": "pending",
        "audit_id": "audit-4",
        "info": {"company_name": "Acme", "company_domain": "acme.com"},
        "is_complete": True,
    }
    human = DummyHumanAgent(follow_up)
    agent = _build_agent(human)
    completion_calls: list[Optional[str]] = []
    dispatch_calls: list[Dict[str, Any]] = []

    async def _fake_dispatch(
        event: Dict[str, Any],
        info: Dict[str, Any],
        result: Dict[str, Any],
        event_id: str,
        *,
        force_internal: bool,
    ) -> None:
        dispatch_calls.append(
            {
                "event": event,
                "info": info,
                "result": result,
                "event_id": event_id,
                "force_internal": force_internal,
            }
        )

    def _record(event_id: Optional[str]) -> None:
        completion_calls.append(event_id)

    monkeypatch.setattr(agent, "_record_missing_info_completion", _record)
    monkeypatch.setattr(agent, "_process_crm_dispatch", _fake_dispatch)

    context = {
        "event": {"id": "evt-6"},
        "info": {"company_name": "Acme"},
        "event_id": "evt-6",
    }

    result = await agent.continue_after_missing_info("audit-1", {}, context)

    assert result is not None
    assert completion_calls == ["evt-6"]
    assert dispatch_calls and dispatch_calls[0]["force_internal"] is True


@pytest.mark.asyncio
async def test_dossier_continuation_decline_short_circuits(monkeypatch: pytest.MonkeyPatch) -> None:
    human = DummyHumanAgent()
    agent = _build_agent(human)
    monkeypatch.setattr(agent, "_process_crm_dispatch", lambda *args, **kwargs: None)

    context = {"event": {"id": "evt-3"}, "info": {"company_name": "Acme"}, "event_id": "evt-3"}

    result = await agent.continue_after_dossier_decision("audit-1", "Declined", context)

    assert result is None
    assert human.requests == []


@pytest.mark.asyncio
async def test_dossier_continuation_dispatches_when_complete(monkeypatch: pytest.MonkeyPatch) -> None:
    human = DummyHumanAgent()
    agent = _build_agent(human)
    dispatch_calls: list[Dict[str, Any]] = []

    async def _fake_dispatch(
        event: Dict[str, Any],
        info: Dict[str, Any],
        result: Dict[str, Any],
        event_id: str,
        *,
        force_internal: bool,
    ) -> None:
        dispatch_calls.append(
            {
                "event": event,
                "info": info,
                "result": result,
                "event_id": event_id,
                "force_internal": force_internal,
            }
        )

    monkeypatch.setattr(agent, "_process_crm_dispatch", _fake_dispatch)

    context = {
        "event": {"id": "evt-4"},
        "info": {"company_name": "Acme", "company_domain": "acme.com"},
        "event_id": "evt-4",
    }

    result = await agent.continue_after_dossier_decision("audit-1", "Approved", context)

    assert result is not None
    assert dispatch_calls and dispatch_calls[0]["force_internal"] is False


@pytest.mark.asyncio
async def test_dossier_continuation_requests_follow_up(monkeypatch: pytest.MonkeyPatch) -> None:
    follow_up = {
        "status": "pending",
        "audit_id": "audit-3",
        "info": {"company_name": "Acme", "company_domain": ""},
    }
    human = DummyHumanAgent(follow_up)
    agent = _build_agent(human)
    pending_calls: list[tuple[str, str, Dict[str, Any]]] = []

    def _on_pending(kind: str, audit_id: str, context: Dict[str, Any]) -> None:
        pending_calls.append((kind, audit_id, context))

    agent.on_pending_audit = _on_pending
    monkeypatch.setattr(agent, "_process_crm_dispatch", lambda *args, **kwargs: None)

    context = {
        "event": {"id": "evt-5"},
        "info": {"company_name": "Acme"},
        "event_id": "evt-5",
    }

    result = await agent.continue_after_dossier_decision("audit-1", "Yes", context)

    assert result is None
    assert len(human.requests) == 1
    assert pending_calls and pending_calls[0][1] == "audit-3"
    assert pending_calls[0][2]["info"]["company_name"] == "Acme"


@pytest.mark.asyncio
async def test_dossier_follow_up_completion(monkeypatch: pytest.MonkeyPatch) -> None:
    follow_up = {
        "status": "pending",
        "audit_id": "audit-5",
        "info": {"company_name": "Acme", "company_domain": "acme.com"},
        "is_complete": True,
    }
    human = DummyHumanAgent(follow_up)
    agent = _build_agent(human)
    dispatch_calls: list[Dict[str, Any]] = []

    async def _fake_dispatch(
        event: Dict[str, Any],
        info: Dict[str, Any],
        result: Dict[str, Any],
        event_id: str,
        *,
        force_internal: bool,
    ) -> None:
        dispatch_calls.append(
            {
                "event": event,
                "info": info,
                "result": result,
                "event_id": event_id,
                "force_internal": force_internal,
            }
        )

    monkeypatch.setattr(agent, "_record_missing_info_completion", lambda event_id: None)
    monkeypatch.setattr(agent, "_process_crm_dispatch", _fake_dispatch)

    context = {
        "event": {"id": "evt-7"},
        "info": {"company_name": "Acme"},
        "event_id": "evt-7",
    }

    result = await agent.continue_after_dossier_decision("audit-1", "Approved", context)

    assert result is not None
    assert dispatch_calls and dispatch_calls[0]["force_internal"] is True
