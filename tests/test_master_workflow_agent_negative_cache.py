from __future__ import annotations

from typing import Any, Dict, Iterable, List

import pytest

from agents.master_workflow_agent import MasterWorkflowAgent
from config.config import settings
from utils.observability import current_run_id_var, generate_run_id


pytestmark = pytest.mark.asyncio


class StubEventAgent:
    def __init__(self, events: Iterable[Dict[str, Any]]):
        self._events = [dict(event) for event in events]

    async def poll(self) -> List[Dict[str, Any]]:
        return [dict(event) for event in self._events]


class StubTriggerAgent:
    def __init__(self, result: Dict[str, Any]):
        self._result = dict(result)

    async def check(self, _event: Dict[str, Any]) -> Dict[str, Any]:
        return dict(self._result)


class StubExtractionAgent:
    async def extract(self, _event: Dict[str, Any]) -> Dict[str, Any]:
        return {"info": {}, "is_complete": False}


class StubCrmAgent:
    def __init__(self) -> None:
        self.sent: List[Dict[str, Any]] = []

    async def send(self, event: Dict[str, Any], info: Dict[str, Any]) -> None:
        self.sent.append({"event": dict(event), "info": dict(info)})


async def _run_agent(
    events: Iterable[Dict[str, Any]],
    *,
    trigger_result: Dict[str, Any],
) -> List[Dict[str, Any]]:
    agent = MasterWorkflowAgent(
        event_agent=StubEventAgent(events),
        trigger_agent=StubTriggerAgent(trigger_result),
        extraction_agent=StubExtractionAgent(),
    )

    run_id = generate_run_id()
    current_run_id_var.set(run_id)
    agent.attach_run(run_id, agent.workflow_log_manager)

    try:
        return await agent.process_all_events()
    finally:
        agent.finalize_run_logs()


async def test_negative_cache_skips_and_reprocesses(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    run_dir = tmp_path / "runs"
    workflow_dir = tmp_path / "workflow"
    run_dir.mkdir(parents=True, exist_ok=True)
    workflow_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(settings, "run_log_dir", run_dir)
    monkeypatch.setattr(settings, "workflow_log_dir", workflow_dir)

    base_event = {
        "id": "evt-1",
        "summary": "Quarterly sync",
        "description": "Discuss roadmap",
    }
    trigger_result = {"trigger": False, "confidence": 0.99}

    first_run = await _run_agent([base_event], trigger_result=trigger_result)
    assert first_run[0]["status"] == "no_trigger"

    second_run = await _run_agent([base_event], trigger_result=trigger_result)
    assert second_run[0]["status"] == "skipped_negative_cache"

    updated_event = dict(base_event)
    updated_event["summary"] = "Quarterly sync updated"

    third_run = await _run_agent([updated_event], trigger_result=trigger_result)
    assert third_run[0]["status"] == "no_trigger"


async def test_processed_event_cache_skips_repeat_dispatch(tmp_path, monkeypatch):
    run_dir = tmp_path / "runs"
    workflow_dir = tmp_path / "workflow"
    run_dir.mkdir(parents=True, exist_ok=True)
    workflow_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(settings, "run_log_dir", run_dir)
    monkeypatch.setattr(settings, "workflow_log_dir", workflow_dir)

    event = {
        "id": "evt-hard-1",
        "updated": "2024-05-01T10:00:00Z",
        "summary": "Urgent expansion",
        "description": "Customer expanding operations.",
    }
    trigger_result = {"trigger": True, "type": "hard", "confidence": 0.99}
    extraction_result = {
        "info": {"company_name": "Acme Corp", "company_domain": "acme.com"},
        "is_complete": True,
        "confidence": 0.95,
    }

    async def _run_positive_agent(crm_agent: StubCrmAgent) -> List[Dict[str, Any]]:
        agent = MasterWorkflowAgent(
            event_agent=StubEventAgent([event]),
            trigger_agent=StubTriggerAgent(trigger_result),
            extraction_agent=StubExtractionAgent(),
            crm_agent=crm_agent,
        )

        async def fake_internal(*args: Any, **kwargs: Any) -> Dict[str, Any]:
            return {"status": "REPORT_REQUIRED"}

        async def fake_precrm(*args: Any, **kwargs: Any) -> None:
            return None

        async def fake_extract(_event: Dict[str, Any]) -> Dict[str, Any]:
            return dict(extraction_result)

        agent._run_internal_research = fake_internal  # type: ignore[assignment]
        agent._execute_precrm_research = fake_precrm  # type: ignore[assignment]
        agent.extraction_agent.extract = fake_extract  # type: ignore[assignment]

        run_id = generate_run_id()
        current_run_id_var.set(run_id)
        agent.attach_run(run_id, agent.workflow_log_manager)

        try:
            return await agent.process_all_events()
        finally:
            agent.finalize_run_logs()

    first_crm_agent = StubCrmAgent()
    first_run = await _run_positive_agent(first_crm_agent)
    assert first_run[0]["status"] == "dispatched_to_crm"
    assert len(first_crm_agent.sent) == 1

    second_crm_agent = StubCrmAgent()
    second_run = await _run_positive_agent(second_crm_agent)
    assert second_run[0]["status"] == "skipped_processed_event"
    assert second_crm_agent.sent == []
