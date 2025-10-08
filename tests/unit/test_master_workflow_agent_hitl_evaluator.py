import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict, List, Optional, Tuple

from utils.email_agent import EmailAgent as SmtpEmailAgent

from agents.master_workflow_agent import MasterWorkflowAgent


class DummyHuman:
    def __init__(self) -> None:
        self.persist_calls: List[Tuple[str, Dict[str, Any]]] = []
        self.dispatch_calls: List[Dict[str, Any]] = []
        self.reminder_calls: List[Tuple[str, str, Any]] = []

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
        message_id = email_agent.send_email(
            operator_email,
            f"HITL request · {run_id}",
            "body",
            headers={"X-Run-ID": run_id, "X-HITL": "1"},
        )
        self.dispatch_calls.append(
            {
                "run_id": run_id,
                "operator": operator_email,
                "context": dict(context),
                "email_agent": email_agent,
                "message_id": message_id,
            }
        )
        return message_id

    def schedule_reminders(
        self, run_id: str, operator_email: str, email_agent: Any
    ) -> None:
        self.reminder_calls.append((run_id, operator_email, email_agent))


class DummyEmailAgent:
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

    def requires_hitl(self, context: Dict[str, Any]) -> Tuple[bool, str]:
        self.calls.append(dict(context))
        return True, "Low confidence score: 0.5 < 0.9"

    def evaluate(self, context: Dict[str, Any]) -> Tuple[bool, str]:  # pragma: no cover
        return self.requires_hitl(context)


def test_master_agent_invokes_evaluator_and_persists_reason(tmp_path) -> None:
    settings = SimpleNamespace(
        HITL_CONFIDENCE_THRESHOLD=0.9,
        HITL_OPERATOR_EMAIL="ops@example.com",
    )
    email_agent = DummyEmailAgent()
    backend = SimpleNamespace(email=email_agent, telemetry=DummyTelemetry())
    agent = MasterWorkflowAgent.__new__(MasterWorkflowAgent)
    agent.settings = settings
    agent.communication_backend = backend
    agent.human_agent = DummyHuman()
    agent.telemetry = backend.telemetry
    agent.hitl_evaluator = RecordingEvaluator()
    agent.run_id = "run-eval-1"
    agent.run_directory = Path(tmp_path)

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
            "missing_optional_fields": None,
            "dossier_status": None,
            "insufficient_context": False,
            "missing_fields": [],
        }
    ]
    assert agent.human_agent.persist_calls == [
        (
            "run-eval-1",
            {
                "company_domain": "acme.test",
                "confidence_score": 0.5,
                "missing_fields": "None",
                "hitl_reason": "Low confidence score: 0.5 < 0.9",
                "hitl_reason_code": "low_confidence",
                "run_id": "run-eval-1",
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
    assert agent.telemetry.events[1] == (
        "info",
        "hitl_request_sent",
        {"run_id": "run-eval-1", "msg_id": "msg-1"},
    )
    assert agent.human_agent.reminder_calls == [
        ("run-eval-1", "ops@example.com", email_agent)
    ]
    artifact = Path(agent.run_directory) / "hitl.json"
    assert artifact.exists(), "HITL artifact should be written"
    payload = json.loads(artifact.read_text())
    assert payload["run_id"] == "run-eval-1"
    assert payload["reason"] == "low_confidence"
    assert email_agent.calls and email_agent.calls[0]["recipient"] == "ops@example.com"


def test_master_agent_builds_smtp_email_agent() -> None:
    agent = MasterWorkflowAgent.__new__(MasterWorkflowAgent)
    agent.settings = SimpleNamespace(
        HITL_OPERATOR_EMAIL="ops@example.com",
        smtp_host="smtp.example.com",
        smtp_port="587",
        smtp_username="mailer@example.com",
        smtp_password="secret",
        smtp_secure="true",
    )
    agent.communication_backend = None
    agent._smtp_email_agent = None  # type: ignore[attr-defined]

    email_agent = agent._resolve_email_agent()

    assert isinstance(email_agent, SmtpEmailAgent)
    assert agent._resolve_email_agent() is email_agent
