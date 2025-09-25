from typing import Any, Dict, Iterable, List

from agents.master_workflow_agent import MasterWorkflowAgent


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

    def poll(self) -> Iterable[Dict[str, Any]]:
        for event in self._events:
            yield event


class DummyTriggerAgent:
    def __init__(self, result: Dict[str, Any]):
        self._result = result

    def check(self, _event: Dict[str, Any]) -> Dict[str, Any]:
        return self._result


class DummyExtractionAgent:
    def __init__(self, response: Dict[str, Any]):
        self._response = response

    def extract(self, _event: Dict[str, Any]) -> Dict[str, Any]:
        return self._response


def _prepare_agent(backend: DummyBackend) -> MasterWorkflowAgent:
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

    def _capture_send(to_event: Dict[str, Any], event_info: Dict[str, Any]) -> None:
        agent._send_calls.append({"event": to_event, "info": event_info})

    agent._send_to_crm_agent = _capture_send  # type: ignore[assignment]
    return agent


def test_soft_trigger_dossier_request_accepted() -> None:
    backend = DummyBackend(
        {"dossier_required": True, "details": {"note": "Yes, please prepare it."}}
    )
    agent = _prepare_agent(backend)

    agent.process_all_events()

    assert len(agent._send_calls) == 1
    assert agent._send_calls[0]["info"]["company_name"] == "Example Corp"

    assert backend.requests, "Backend should have been invoked"
    first_request = backend.requests[0]
    assert first_request["contact"]["email"] == "organizer@example.com"
    assert "Soft trigger meeting" in first_request["subject"]


def test_soft_trigger_dossier_request_declined() -> None:
    backend = DummyBackend(
        {"dossier_required": False, "details": {"note": "No dossier required."}}
    )
    agent = _prepare_agent(backend)

    agent.process_all_events()

    assert agent._send_calls == []
    assert len(backend.requests) == 1
    assert backend.requests[0]["info"]["company_name"] == "Example Corp"
