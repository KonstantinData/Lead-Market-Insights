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
