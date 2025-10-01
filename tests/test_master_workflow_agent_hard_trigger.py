import asyncio
from typing import Any, Dict, Iterable

from agents.master_workflow_agent import MasterWorkflowAgent


class DummyEventAgent:
    def __init__(self, events: Iterable[Dict[str, Any]]):
        self._events = list(events)

    async def poll(self) -> Iterable[Dict[str, Any]]:
        return list(self._events)


class DummyTriggerAgent:
    def __init__(self, result: Dict[str, Any]):
        self._result = result

    async def check(self, _event: Dict[str, Any]) -> Dict[str, Any]:
        return dict(self._result)


class DummyExtractionAgent:
    def __init__(self, response: Dict[str, Any]):
        self._response = response

    def extract(self, _event: Dict[str, Any]) -> Dict[str, Any]:
        return dict(self._response)


def test_hard_trigger_with_complete_info_dispatches_without_unhandled_state() -> None:
    event = {"id": "event-001", "summary": "Hard trigger meeting"}
    info = {"company_name": "Example Corp", "company_domain": "example.com"}

    agent = MasterWorkflowAgent(
        event_agent=DummyEventAgent([event]),
        trigger_agent=DummyTriggerAgent({"trigger": True, "type": "hard"}),
        extraction_agent=DummyExtractionAgent({"info": info, "is_complete": True}),
    )

    dispatched: Dict[str, Any] = {"called": False}

    async def _fake_process_crm_dispatch(
        _event: Dict[str, Any],
        _info: Dict[str, Any],
        event_result: Dict[str, Any],
        _event_id: Any,
        *,
        force_internal: bool,
    ) -> None:
        dispatched["called"] = True
        dispatched["force_internal"] = force_internal
        event_result["status"] = "dispatched_to_crm"
        event_result["crm_payload"] = {"info": _info}

    agent._process_crm_dispatch = _fake_process_crm_dispatch  # type: ignore[assignment]

    try:
        results = asyncio.run(agent.process_all_events())
    finally:
        agent.finalize_run_logs()

    assert dispatched["called"] is True
    assert dispatched["force_internal"] is False
    assert results[0]["status"] == "dispatched_to_crm"
    assert results[0]["crm_payload"] == {"info": info}
