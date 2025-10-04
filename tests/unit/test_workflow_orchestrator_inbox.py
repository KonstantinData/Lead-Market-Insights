import asyncio
from dataclasses import dataclass
from typing import Any, Dict, Optional

import pytest

from agents.workflow_orchestrator import WorkflowOrchestrator
from polling.inbox_agent import InboxMessage
from unittest.mock import AsyncMock


class DummyAuditLog:
    def __init__(self) -> None:
        self.records: list[Dict[str, Any]] = []
        self.responses: set[str] = set()

    def record(
        self,
        *,
        event_id: Optional[str],
        request_type: str,
        stage: str,
        responder: str,
        outcome: str,
        payload: Optional[Dict[str, Any]] = None,
        audit_id: Optional[str] = None,
    ) -> str:
        entry = {
            "event_id": event_id,
            "request_type": request_type,
            "stage": stage,
            "responder": responder,
            "outcome": outcome,
            "payload": payload,
            "audit_id": audit_id or "generated",
        }
        self.records.append(entry)
        if stage == "response" and audit_id:
            self.responses.add(audit_id)
        return entry["audit_id"]

    def has_response(self, audit_id: str) -> bool:
        return audit_id in self.responses


class DummyReminder:
    def __init__(self) -> None:
        self.cancelled: list[str] = []

    def cancel_for_audit(self, audit_id: str) -> None:
        self.cancelled.append(audit_id)


class DummyHuman:
    def __init__(self) -> None:
        self.reminder_escalation = DummyReminder()


@dataclass
class DummyMasterAgent:
    log_filename: str = "log.txt"
    storage_agent: Any = None

    def __post_init__(self) -> None:
        self.audit_log = DummyAuditLog()
        self.human_agent = DummyHuman()
        self.continue_after_missing_info = AsyncMock()
        self.continue_after_dossier_decision = AsyncMock()
        self.on_pending_audit = None

    async def aclose(self) -> None:  # pragma: no cover - optional cleanup
        pass


class DummyInboxAgent:
    def __init__(self) -> None:
        self.handlers: list[Any] = []
        self.started: list[Optional[float]] = []

    def register_handler(self, handler: Any) -> None:
        self.handlers.append(handler)

    async def start_polling_loop(self, *, interval_seconds: Optional[float] = None) -> None:
        self.started.append(interval_seconds)
        await asyncio.sleep(0)


@pytest.fixture(autouse=True)
def _patch_helpers(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "agents.workflow_orchestrator.configure_observability", lambda: None
    )

    class _Recorder:
        def __init__(self) -> None:
            self.calls: list[tuple[str, Optional[str], str]] = []

        def record_step(
            self, run_id: str, event_id: Optional[str], step: str, *, extra: Any = None
        ) -> bool:
            self.calls.append((run_id, event_id, step))
            return True

        def should_write_manifest(self, run_id: str) -> bool:
            return True

        def clear_run(self, run_id: str) -> None:
            pass

    recorder = _Recorder()
    monkeypatch.setattr(
        "agents.workflow_orchestrator.workflow_step_recorder", recorder
    )
    monkeypatch.setattr(
        "agents.master_workflow_agent.workflow_step_recorder", recorder
    )


@pytest.fixture
def orchestrator(monkeypatch: pytest.MonkeyPatch) -> WorkflowOrchestrator:
    inbox = DummyInboxAgent()
    monkeypatch.setattr(
        WorkflowOrchestrator,
        "_create_inbox_agent",
        lambda self: inbox,
    )
    master = DummyMasterAgent()
    orch = WorkflowOrchestrator(run_id="run-1", master_agent=master)
    orch._start_inbox_polling = lambda: None  # avoid creating background task
    return orch


@pytest.mark.asyncio
async def test_on_pending_records_context(orchestrator: WorkflowOrchestrator) -> None:
    orchestrator._on_pending_audit("missing_info", "audit-1", {"event_id": "evt"})

    assert "audit-1" in orchestrator._pending_audits
    assert orchestrator._pending_audits["audit-1"]["kind"] == "missing_info"


@pytest.mark.asyncio
async def test_on_pending_skips_without_inbox(orchestrator: WorkflowOrchestrator) -> None:
    orchestrator.inbox_agent = None

    orchestrator._on_pending_audit("missing_info", "audit-2", {"event_id": "evt"})

    assert "audit-2" not in orchestrator._pending_audits


def test_on_pending_skips_when_resolved(orchestrator: WorkflowOrchestrator) -> None:
    orchestrator._resolved_audits.add("audit-existing")

    orchestrator._on_pending_audit("missing_info", "audit-existing", {"event_id": "evt"})

    assert "audit-existing" not in orchestrator._pending_audits


@pytest.mark.asyncio
async def test_handle_missing_info_reply_continues_workflow(
    orchestrator: WorkflowOrchestrator,
) -> None:
    orchestrator._on_pending_audit(
        "missing_info",
        "audit-1",
        {"event_id": "evt", "event": {"id": "evt"}, "info": {"company_name": "Acme"}},
    )

    message = InboxMessage(
        id="msg-1",
        subject="Re: Request",
        sender="organizer@example.com",
        body="company_domain: acme.com",
    )

    await orchestrator._handle_inbox_reply(message, "audit-1")

    master = orchestrator.master_agent
    assert master.continue_after_missing_info.await_count == 1
    assert master.human_agent.reminder_escalation.cancelled == ["audit-1"]
    assert master.audit_log.records and master.audit_log.records[0]["stage"] == "response"
    assert "audit-1" in orchestrator._resolved_audits

    await orchestrator._handle_inbox_reply(message, "audit-1")
    assert master.continue_after_missing_info.await_count == 1


@pytest.mark.asyncio
async def test_handle_reply_without_audit_id_is_ignored(
    orchestrator: WorkflowOrchestrator,
) -> None:
    message = InboxMessage(
        id="msg-no-audit",
        subject="Re: Request",
        sender="organizer@example.com",
        body="ignored",
    )

    await orchestrator._handle_inbox_reply(message, None)

    assert orchestrator.master_agent.continue_after_missing_info.await_count == 0


@pytest.mark.asyncio
async def test_handle_reply_for_resolved_audit_is_ignored(
    orchestrator: WorkflowOrchestrator,
) -> None:
    orchestrator._pending_audits["audit-resolved"] = {
        "kind": "missing_info",
        "context": {},
        "resolved": True,
    }

    message = InboxMessage(
        id="msg-resolved",
        subject="Re: Done",
        sender="organizer@example.com",
        body="company_domain: example.com",
    )

    await orchestrator._handle_inbox_reply(message, "audit-resolved")

    assert "audit-resolved" not in orchestrator._pending_audits


@pytest.mark.asyncio
async def test_handle_dossier_reply_invokes_correct_continuation(
    orchestrator: WorkflowOrchestrator,
) -> None:
    orchestrator._on_pending_audit(
        "dossier",
        "audit-2",
        {"event_id": "evt-2", "event": {}, "info": {}},
    )
    message = InboxMessage(
        id="msg-2",
        subject="Approved",
        sender="organizer@example.com",
        body="Yes, go ahead",
    )

    await orchestrator._handle_inbox_reply(message, "audit-2")

    master = orchestrator.master_agent
    assert master.continue_after_dossier_decision.await_count == 1


def test_is_audit_resolved_uses_audit_log(orchestrator: WorkflowOrchestrator) -> None:
    orchestrator.master_agent.audit_log.responses.add("audit-3")

    assert orchestrator._is_audit_resolved("audit-3") is True
    assert "audit-3" in orchestrator._resolved_audits


@pytest.mark.asyncio
async def test_handle_reply_applies_mask(orchestrator: WorkflowOrchestrator) -> None:
    orchestrator._on_pending_audit(
        "missing_info",
        "audit-4",
        {"event_id": "evt-4", "event": {}, "info": {}},
    )

    def _mask(value: Any) -> Any:
        if isinstance(value, dict):
            return {"masked": True}
        return "masked"

    orchestrator.master_agent._mask_for_logging = _mask  # type: ignore[attr-defined]

    message = InboxMessage(
        id="msg-4",
        subject="Info",
        sender="organizer@example.com",
        body="field: value",
    )

    await orchestrator._handle_inbox_reply(message, "audit-4")

    record = orchestrator.master_agent.audit_log.records[-1]
    assert record["payload"] == {"masked": True}
    assert record["responder"] == "masked"


@pytest.mark.asyncio
async def test_handle_reply_logs_mask_failure(
    orchestrator: WorkflowOrchestrator, caplog: pytest.LogCaptureFixture
) -> None:
    orchestrator._on_pending_audit(
        "missing_info",
        "audit-mask",
        {"event_id": "evt-mask", "event": {}, "info": {}},
    )

    def _mask(_value: Any) -> Any:
        raise RuntimeError("mask failure")

    orchestrator.master_agent._mask_for_logging = _mask  # type: ignore[attr-defined]

    message = InboxMessage(
        id="msg-mask",
        subject="Info",
        sender="organizer@example.com",
        body="field: value",
    )

    with caplog.at_level("ERROR"):
        await orchestrator._handle_inbox_reply(message, "audit-mask")

    assert any("mask inbox payload" in record.message for record in caplog.records)


@pytest.mark.asyncio
async def test_handle_reply_master_missing_marks_resolved(
    orchestrator: WorkflowOrchestrator,
) -> None:
    orchestrator._on_pending_audit(
        "missing_info",
        "audit-none",
        {"event_id": "evt-5", "event": {}, "info": {}},
    )

    orchestrator.master_agent = None

    message = InboxMessage(
        id="msg-5",
        subject="Re: Missing Info",
        sender="organizer@example.com",
        body="details",
    )

    await orchestrator._handle_inbox_reply(message, "audit-none")

    assert "audit-none" in orchestrator._resolved_audits
    assert "audit-none" not in orchestrator._pending_audits


@pytest.mark.asyncio
async def test_handle_reply_records_failure(orchestrator: WorkflowOrchestrator) -> None:
    orchestrator._on_pending_audit(
        "missing_info",
        "audit-record",
        {"event_id": "evt-record", "event": {}, "info": {}},
    )

    def _raise_record(*args: Any, **kwargs: Any) -> None:
        raise RuntimeError("write failure")

    orchestrator.master_agent.audit_log.record = _raise_record  # type: ignore[attr-defined]

    message = InboxMessage(
        id="msg-record",
        subject="Re: Info",
        sender="organizer@example.com",
        body="field: value",
    )

    await orchestrator._handle_inbox_reply(message, "audit-record")

    assert "audit-record" in orchestrator._resolved_audits


@pytest.mark.asyncio
async def test_handle_reply_cancel_failure(orchestrator: WorkflowOrchestrator) -> None:
    orchestrator._on_pending_audit(
        "missing_info",
        "audit-cancel",
        {"event_id": "evt-cancel", "event": {}, "info": {}},
    )

    class ExplodingReminder:
        def cancel_for_audit(self, audit_id: str) -> None:
            raise RuntimeError("boom")

    orchestrator.master_agent.human_agent.reminder_escalation = ExplodingReminder()  # type: ignore[assignment]

    message = InboxMessage(
        id="msg-cancel",
        subject="Re: Info",
        sender="organizer@example.com",
        body="field: value",
    )

    await orchestrator._handle_inbox_reply(message, "audit-cancel")

    assert "audit-cancel" in orchestrator._resolved_audits
