import asyncio
import contextlib
from dataclasses import dataclass
from typing import Any, Dict, Optional

import pytest
from unittest.mock import AsyncMock, MagicMock

from agents.master_workflow_agent import MasterWorkflowAgent
from agents.workflow_orchestrator import WorkflowOrchestrator
from polling.inbox_agent import InboxMessage
from reminders.reminder_escalation import ReminderEscalation


class _StepRecorder:
    def __init__(self) -> None:
        self.calls: list[tuple[str, Optional[str], str]] = []

    def record_step(
        self, run_id: str, event_id: Optional[str], step: str, *, extra: Any = None
    ) -> bool:
        self.calls.append((run_id, event_id, step))
        return True

    def should_write_manifest(self, run_id: str) -> bool:
        return True

    def clear_run(self, run_id: str) -> None:  # pragma: no cover - unused helper
        pass


@pytest.fixture(autouse=True)
def _patch_observability(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "agents.workflow_orchestrator.configure_observability", lambda: None
    )
    recorder = _StepRecorder()
    monkeypatch.setattr(
        "agents.workflow_orchestrator.workflow_step_recorder", recorder
    )
    monkeypatch.setattr("agents.master_workflow_agent.workflow_step_recorder", recorder)
    monkeypatch.setattr(
        "agents.master_workflow_agent.observe_operation",
        lambda *args, **kwargs: contextlib.nullcontext(),
    )
    monkeypatch.setattr(
        "agents.master_workflow_agent.record_hitl_outcome", lambda *args, **kwargs: None
    )


class DummyReminder:
    def __init__(self) -> None:
        self.cancelled: list[str] = []

    def cancel_for_audit(self, audit_id: str) -> None:
        self.cancelled.append(audit_id)


class DummyHuman:
    def __init__(self, *, follow_up: Optional[Dict[str, Any]] = None) -> None:
        self._follow_up = follow_up
        self.requests: list[Dict[str, Any]] = []
        self.reminder_escalation = DummyReminder()

    def request_info(self, event: Dict[str, Any], extracted: Dict[str, Any]) -> Dict[str, Any]:
        self.requests.append({"event": event, "extracted": extracted})
        data = self._follow_up or {}
        return dict(data)


@dataclass
class DummyInboxAgent:
    handlers: list[Any]

    def __init__(self) -> None:
        self.handlers = []

    def register_handler(self, handler: Any) -> None:
        self.handlers.append(handler)


class _ImmediateInboxAgent:
    def __init__(self) -> None:
        self.handler: Optional[Any] = None

    def register_handler(self, handler: Any) -> None:
        self.handler = handler


def _build_master(human: DummyHuman) -> MasterWorkflowAgent:
    master = MasterWorkflowAgent.__new__(MasterWorkflowAgent)
    master.run_id = "run-e2e"
    master.human_agent = human
    master.on_pending_audit = None
    master.audit_log = None
    master.log_filename = "master.log"
    master.storage_agent = None
    master._process_crm_dispatch = AsyncMock()
    master._record_missing_info_completion = lambda event_id: master._completions.append(
        event_id
    )
    master._completions = []  # type: ignore[attr-defined]
    return master


def _build_orchestrator(
    master: MasterWorkflowAgent, monkeypatch: pytest.MonkeyPatch
) -> WorkflowOrchestrator:
    inbox = DummyInboxAgent()
    monkeypatch.setattr(
        WorkflowOrchestrator,
        "_create_inbox_agent",
        lambda self: inbox,
    )
    orchestrator = WorkflowOrchestrator(run_id="run-e2e", master_agent=master)
    orchestrator._start_inbox_polling = lambda: None
    return orchestrator


def _pending_context(info: Dict[str, Any]) -> Dict[str, Any]:
    domain_hint = info.get("company_domain") or "acme.com"
    return {
        "event": {
            "id": "evt-123",
            "creator": "organizer@example.com",
            "summary": f"Follow-up regarding {domain_hint}",
        },
        "info": info,
        "event_id": "evt-123",
    }


@pytest.mark.asyncio
async def test_hitl_pending_reply_continues_workflow(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    inbox = _ImmediateInboxAgent()
    monkeypatch.setattr(
        WorkflowOrchestrator,
        "_create_inbox_agent",
        lambda self: inbox,
    )

    human_agent = MagicMock()
    human_agent.reminder_escalation = MagicMock()
    human_agent.reminder_escalation.cancel_for_audit = MagicMock()

    class _StubMaster:
        def __init__(self) -> None:
            self.log_filename = "stub.log"
            self.storage_agent = None
            self.human_agent = human_agent
            self.audit_log = MagicMock()
            self.audit_log.record = MagicMock()
            self.audit_log.has_response = MagicMock(return_value=False)
            self.on_pending_audit = None
            self.continue_after_missing_info = AsyncMock()

    master = _StubMaster()
    orchestrator = WorkflowOrchestrator(run_id="run-test", master_agent=master)
    orchestrator._start_inbox_polling = lambda: None

    assert inbox.handler is not None

    orchestrator.on_pending("missing_info", "A123", {"run_id": "R1"})

    message = InboxMessage(
        id="msg-test",
        subject="Re: Missing Info",
        sender="organizer@example.com",
        body="company_name: TestCo\nweb_domain: test.co",
    )

    await inbox.handler(message, "A123")

    human_agent.reminder_escalation.cancel_for_audit.assert_called_once_with("A123")
    master.continue_after_missing_info.assert_awaited_once()
    args = master.continue_after_missing_info.await_args.args
    assert args[0] == "A123"
    assert args[1] == {"company_name": "TestCo", "web_domain": "test.co"}
    assert args[2]["run_id"] == "R1"


@pytest.mark.asyncio
async def test_missing_info_reply_merges_fields_and_dispatches(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    human = DummyHuman()
    master = _build_master(human)
    orchestrator = _build_orchestrator(master, monkeypatch)

    orchestrator._on_pending_audit(
        "missing_info", "audit-missing", _pending_context({"company_name": "Acme"})
    )

    message = InboxMessage(
        id="msg-merge",
        subject="Re: Additional details",
        sender="organizer@example.com",
        body="Web Domain: acme.com",
    )

    await orchestrator._handle_inbox_reply(message, "audit-missing")

    master._process_crm_dispatch.assert_awaited_once()
    args = master._process_crm_dispatch.await_args
    event, info, result, event_id = args.args[:4]
    kwargs = args.kwargs
    assert event["id"] == "evt-123"
    assert info["company_name"] == "Acme"
    assert info["company_domain"] == "acme.com"
    assert result["status"] == "missing_info_followup"
    assert event_id == "evt-123"
    assert kwargs.get("force_internal") is True
    assert human.requests == []
    assert human.reminder_escalation.cancelled == ["audit-missing"]
    assert master._completions == ["evt-123"]  # type: ignore[attr-defined]
    assert "audit-missing" not in orchestrator._pending_audits
    assert "audit-missing" in orchestrator._resolved_audits


@pytest.mark.asyncio
async def test_dossier_reply_dispatches_when_complete(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    human = DummyHuman()
    master = _build_master(human)
    orchestrator = _build_orchestrator(master, monkeypatch)

    orchestrator._on_pending_audit(
        "dossier",
        "audit-dossier",
        _pending_context({"company_name": "Acme", "company_domain": "acme.com"}),
    )

    message = InboxMessage(
        id="msg-approve",
        subject="Re: Proceed",
        sender="organizer@example.com",
        body="Yes, looks good",
    )

    await orchestrator._handle_inbox_reply(message, "audit-dossier")

    master._process_crm_dispatch.assert_awaited_once()
    args = master._process_crm_dispatch.await_args
    info = args.args[1]
    kwargs = args.kwargs
    assert info["company_domain"] == "acme.com"
    assert kwargs.get("force_internal") is False
    assert human.requests == []
    assert human.reminder_escalation.cancelled == ["audit-dossier"]
    assert master._completions == []  # type: ignore[attr-defined]
    assert "audit-dossier" not in orchestrator._pending_audits


@pytest.mark.asyncio
async def test_dossier_reply_requests_follow_up_when_incomplete(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    follow_up = {
        "status": "pending",
        "audit_id": "audit-follow",
        "info": {"company_name": "Acme", "company_domain": ""},
    }
    human = DummyHuman(follow_up=follow_up)
    master = _build_master(human)
    orchestrator = _build_orchestrator(master, monkeypatch)

    orchestrator._on_pending_audit(
        "dossier",
        "audit-original",
        _pending_context({"company_name": "Acme", "company_domain": ""}),
    )

    message = InboxMessage(
        id="msg-more-info",
        subject="Re: Need more info",
        sender="organizer@example.com",
        body="Yes",
    )

    await orchestrator._handle_inbox_reply(message, "audit-original")

    master._process_crm_dispatch.assert_awaited_once()
    dispatch_args = master._process_crm_dispatch.await_args
    assert dispatch_args.kwargs.get("force_internal") is False
    assert len(human.requests) == 0
    assert human.reminder_escalation.cancelled == ["audit-original"]
    assert "audit-follow" not in orchestrator._pending_audits
    assert master._completions == []  # type: ignore[attr-defined]


@pytest.mark.asyncio
async def test_dossier_reply_decline_short_circuits(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    human = DummyHuman()
    master = _build_master(human)
    orchestrator = _build_orchestrator(master, monkeypatch)

    orchestrator._on_pending_audit(
        "dossier",
        "audit-decline",
        _pending_context({"company_name": "Acme", "company_domain": ""}),
    )

    message = InboxMessage(
        id="msg-decline",
        subject="Re: No thanks",
        sender="organizer@example.com",
        body="No",
    )

    await orchestrator._handle_inbox_reply(message, "audit-decline")

    master._process_crm_dispatch.assert_not_awaited()
    assert human.requests == []
    assert human.reminder_escalation.cancelled == ["audit-decline"]
    assert "audit-decline" not in orchestrator._pending_audits


class DummyEmailAgent:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, str]] = []

    async def send_email_async(self, recipient: str, subject: str, body: str) -> bool:
        self.calls.append((recipient, subject, body))
        return True


@pytest.mark.asyncio
async def test_admin_escalation_and_recurring_reminders_cancel(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    email_agent = DummyEmailAgent()
    reminder = ReminderEscalation(email_agent)

    sent = await reminder.escalate(
        "admin@example.com",
        "Escalation required",
        "Please review pending audit",
        metadata={"audit_id": "audit-escalate"},
    )
    assert sent is True
    assert email_agent.calls == [
        ("admin@example.com", "Escalation required", "Please review pending audit")
    ]

    task = reminder.schedule_admin_recurring_reminders(
        "admin@example.com",
        "Reminder",
        "Still waiting on organiser",
        interval_hours=0.00001,
        metadata={"audit_id": "audit-escalate"},
    )

    await asyncio.sleep(0.05)
    assert len(email_agent.calls) >= 2

    reminder.cancel_for_audit("audit-escalate")

    with contextlib.suppress(asyncio.CancelledError):
        await task

    sent_so_far = len(email_agent.calls)
    await asyncio.sleep(0.05)
    assert len(email_agent.calls) == sent_so_far
    assert "audit-escalate" not in reminder._audit_tasks
    assert task not in reminder._tasks
