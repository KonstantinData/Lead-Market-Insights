from types import SimpleNamespace
from typing import Any, Dict, List, Optional, Tuple

import pytest

from agents.master_workflow_agent import MasterWorkflowAgent


class DummyHumanAgent:
    def __init__(self) -> None:
        self.persisted: List[Tuple[str, Dict[str, Any]]] = []
        self.dispatched: List[Dict[str, Any]] = []

    def persist_pending_request(self, run_id: str, context: Dict[str, Any]) -> None:
        self.persisted.append((run_id, dict(context)))

    def dispatch_request_email(
        self,
        *,
        run_id: str,
        operator_email: str,
        context: Dict[str, Any],
        email_agent: Any,
    ) -> str:
        self.dispatched.append(
            {
                "run_id": run_id,
                "operator": operator_email,
                "context": dict(context),
                "email_agent": email_agent,
            }
        )
        return "msg-123"


class DummyTelemetry:
    def __init__(self) -> None:
        self.events: List[Tuple[str, str, Dict[str, Any]]] = []

    def info(self, event: str, payload: Dict[str, Any]) -> None:
        self.events.append(("info", event, dict(payload)))

    def warn(self, event: str, payload: Dict[str, Any]) -> None:
        self.events.append(("warn", event, dict(payload)))


def _build_master(
    human_agent: DummyHumanAgent,
    *,
    backend: Any = None,
    telemetry: Optional[DummyTelemetry] = None,
) -> MasterWorkflowAgent:
    agent = MasterWorkflowAgent.__new__(MasterWorkflowAgent)
    agent.human_agent = human_agent
    agent.communication_backend = backend
    if telemetry is not None:
        agent.telemetry = telemetry
    else:
        if hasattr(agent, "telemetry"):
            delattr(agent, "telemetry")
    return agent


def test_trigger_hitl_persists_and_dispatches() -> None:
    human = DummyHumanAgent()
    backend = SimpleNamespace(email=object())
    telemetry = DummyTelemetry()
    agent = _build_master(human, backend=backend, telemetry=telemetry)

    message_id = agent.trigger_hitl(
        "run-123",
        {"company": "ACME"},
        "ops@example.com",
    )

    assert message_id == "msg-123"
    assert human.persisted == [("run-123", {"company": "ACME"})]
    assert human.dispatched and human.dispatched[0]["run_id"] == "run-123"
    assert human.dispatched[0]["operator"] == "ops@example.com"
    assert human.dispatched[0]["email_agent"] is backend.email
    assert telemetry.events[-1] == (
        "info",
        "hitl_request_sent",
        {"run_id": "run-123", "msg_id": "msg-123"},
    )


def test_trigger_hitl_without_email_backend_raises() -> None:
    human = DummyHumanAgent()
    telemetry = DummyTelemetry()
    agent = _build_master(human, backend=SimpleNamespace(), telemetry=telemetry)

    with pytest.raises(RuntimeError) as exc:
        agent.trigger_hitl("run-999", {"company": "ACME"}, "ops@example.com")

    assert "email" in str(exc.value).lower()
    assert human.persisted == []
    assert human.dispatched == []
    assert telemetry.events == []


def test_on_hitl_decision_routes_to_branch_handlers() -> None:
    telemetry = DummyTelemetry()
    agent = MasterWorkflowAgent.__new__(MasterWorkflowAgent)
    agent.telemetry = telemetry

    approvals: List[str] = []
    changes: List[Tuple[str, Dict[str, Any]]] = []
    declines: List[str] = []

    agent._advance_after_approval = approvals.append  # type: ignore[attr-defined]

    def _record_change(run_id: str, extra: Dict[str, Any]) -> None:
        changes.append((run_id, dict(extra)))

    agent._requeue_research_with_changes = _record_change  # type: ignore[attr-defined]
    agent._close_run = declines.append  # type: ignore[attr-defined]

    agent.on_hitl_decision("run-1", {"status": "approved"})
    agent.on_hitl_decision(
        "run-2",
        {"status": "change_requested", "extra": {"company_domain": "acme.com"}},
    )
    agent.on_hitl_decision("run-3", {"status": "declined"})
    agent.on_hitl_decision("run-4", {"status": "mystery"})

    assert approvals == ["run-1"]
    assert changes == [("run-2", {"company_domain": "acme.com"})]
    assert declines == ["run-3"]
    assert telemetry.events[0] == ("info", "hitl_approved", {"run_id": "run-1"})
    assert telemetry.events[1] == (
        "info",
        "hitl_change",
        {"run_id": "run-2", "extra": {"company_domain": "acme.com"}},
    )
    assert telemetry.events[2] == ("info", "hitl_declined", {"run_id": "run-3"})
    assert telemetry.events[3] == (
        "warn",
        "hitl_unknown_decision",
        {"run_id": "run-4", "status": "mystery"},
    )
