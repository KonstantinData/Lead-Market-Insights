from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict, List, Optional

from agents.hitl_decision_evaluator import HITLDecisionEvaluator
from agents.master_workflow_agent import MasterWorkflowAgent


class StubEmailAgent:
    def __init__(self) -> None:
        self.calls: List[Dict[str, Any]] = []

    def send_email(
        self, recipient: str, subject: str, body: str, headers: Optional[Dict[str, Any]] = None
    ) -> str:
        self.calls.append(
            {
                "recipient": recipient,
                "subject": subject,
                "body": body,
                "headers": dict(headers or {}),
            }
        )
        return "stub-message"


class StubHumanAgent:
    def __init__(self) -> None:
        self.persisted: List[Dict[str, Any]] = []
        self.dispatched: List[Dict[str, Any]] = []
        self.reminders: List[Dict[str, Any]] = []

    def persist_pending_request(self, run_id: str, context: Dict[str, Any]) -> None:
        self.persisted.append({"run_id": run_id, "context": dict(context)})

    def dispatch_request_email(
        self,
        *,
        run_id: str,
        operator_email: str,
        context: Dict[str, Any],
        email_agent: Any,
    ) -> str:
        message_id = email_agent.send_email(
            operator_email,
            f"HITL Approval · {run_id}",
            "body",
            headers={"X-Run-ID": run_id, "X-HITL": "1"},
        )
        self.dispatched.append(
            {
                "run_id": run_id,
                "operator": operator_email,
                "context": dict(context),
                "message_id": message_id,
            }
        )
        return message_id

    def schedule_reminders(
        self, run_id: str, operator_email: str, email_agent: Any
    ) -> None:
        self.reminders.append(
            {
                "run_id": run_id,
                "operator": operator_email,
                "email_agent": email_agent,
            }
        )


class StubTelemetry:
    def __init__(self) -> None:
        self.events: List[Dict[str, Any]] = []

    def info(self, event: str, payload: Dict[str, Any]) -> None:
        self.events.append({"level": "info", "event": event, "payload": dict(payload)})

    def warn(self, event: str, payload: Dict[str, Any]) -> None:
        self.events.append({"level": "warn", "event": event, "payload": dict(payload)})


def test_fake_event_triggers_hitl_request(tmp_path) -> None:
    run_directory = Path(tmp_path)
    email_agent = StubEmailAgent()
    telemetry = StubTelemetry()
    backend = SimpleNamespace(email=email_agent, telemetry=telemetry)

    agent = MasterWorkflowAgent.__new__(MasterWorkflowAgent)
    agent.settings = SimpleNamespace(HITL_OPERATOR_EMAIL="ops@example.com")
    agent.communication_backend = backend
    agent.telemetry = telemetry
    agent.human_agent = StubHumanAgent()
    agent.hitl_evaluator = HITLDecisionEvaluator()
    agent.run_id = "run-hitl-integration"
    agent.run_directory = run_directory

    event_result = {"research": {}, "status": "received"}
    context_payload = {
        "company_domain": "acme.test",
        "company_in_crm": True,
        "attachments_in_crm": False,
    }
    event = {"organizer": {"email": "organizer@example.com"}}

    triggered = agent._evaluate_hitl_condition(
        event_result,
        context_payload,
        event_id="evt-1",
        dossier_result=None,
        event=event,
        crm_result=None,
    )

    assert triggered is True
    assert event_result["status"] == "hitl_pending"
    assert any(e["event"] == "hitl_request_sent" for e in telemetry.events)
    assert email_agent.calls and email_agent.calls[0]["recipient"] == "ops@example.com"
    assert agent.human_agent.reminders == [
        {
            "run_id": "run-hitl-integration",
            "operator": "ops@example.com",
            "email_agent": email_agent,
        }
    ]

    artifact = run_directory / "hitl.json"
    assert artifact.exists()

    persisted_context = agent.human_agent.persisted[0]["context"]
    assert persisted_context["hitl_reason_code"] == "crm_missing_attachments"