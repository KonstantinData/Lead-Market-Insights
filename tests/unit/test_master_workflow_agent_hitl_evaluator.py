from types import SimpleNamespace
from typing import Any, Dict, List, Tuple

from agents.master_workflow_agent import MasterWorkflowAgent


class DummyHuman:
    def __init__(self) -> None:
        self.persist_calls: List[Tuple[str, Dict[str, Any]]] = []
        self.dispatch_calls: List[Dict[str, Any]] = []

    def persist_pending_request(self, run_id: str, context: Dict[str, Any]) -> None:
        self.persist_calls.append((run_id, dict(context)))

    def dispatch_request_email(
        self,
        *,
        run_id: str,
        operator_email: str,
        context: Dict[str, Any],
        email_agent: Any,
    ) -> str:
        self.dispatch_calls.append(
            {
                "run_id": run_id,
                "operator": operator_email,
                "context": dict(context),
                "email_agent": email_agent,
            }
        )
        return "msg-1"


class DummyTelemetry:
    def __init__(self) -> None:
        self.events: List[Tuple[str, str, Dict[str, Any]]] = []

    def info(self, event: str, payload: Dict[str, Any]) -> None:
        self.events.append(("info", event, dict(payload)))

    def warn(self, event: str, payload: Dict[str, Any]) -> None:
        self.events.append(("warn", event, dict(payload)))


class RecordingEvaluator:
    def __init__(self) -> None:
        self.calls: List[Dict[str, Any]] = []

    def evaluate(self, context: Dict[str, Any]) -> Tuple[bool, str]:
        self.calls.append(dict(context))
        return True, "Low confidence score: 0.5 < 0.9"


def test_master_agent_invokes_evaluator_and_persists_reason() -> None:
    settings = SimpleNamespace(
        HITL_CONFIDENCE_THRESHOLD=0.9,
        HITL_OPERATOR_EMAIL="ops@example.com",
    )
    agent = MasterWorkflowAgent.__new__(MasterWorkflowAgent)
    agent.settings = settings
    agent.communication_backend = SimpleNamespace(email=object())
    agent.human_agent = DummyHuman()
    agent.telemetry = DummyTelemetry()
    agent.hitl_evaluator = RecordingEvaluator()

    message_id = agent.trigger_hitl(
        "run-eval-1",
        {"company_domain": "acme.test", "confidence_score": 0.5},
    )

    assert message_id == "msg-1"
    assert agent.hitl_evaluator.calls == [
        {
            "company_domain": "acme.test",
            "confidence_score": 0.5,
            "company_in_crm": None,
            "attachments_in_crm": None,
        }
    ]
    assert agent.human_agent.persist_calls == [
        (
            "run-eval-1",
            {
                "company_domain": "acme.test",
                "confidence_score": 0.5,
                "hitl_reason": "Low confidence score: 0.5 < 0.9",
            },
        )
    ]
    assert agent.human_agent.dispatch_calls and agent.human_agent.dispatch_calls[0][
        "context"
    ]["hitl_reason"].startswith("Low confidence")
    assert agent.telemetry.events[0] == (
        "info",
        "hitl_required",
        {"run_id": "run-eval-1", "reason": "Low confidence score: 0.5 < 0.9"},
    )
