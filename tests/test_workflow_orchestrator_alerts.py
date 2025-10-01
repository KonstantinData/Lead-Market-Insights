from __future__ import annotations

import pytest

from agents.alert_agent import AlertSeverity
from agents.workflow_orchestrator import WorkflowOrchestrator


pytestmark = pytest.mark.asyncio


class DummyAlertAgent:
    def __init__(self):
        self.calls = []

    def send_alert(self, message, severity, context=None):
        self.calls.append({
            "message": message,
            "severity": severity,
            "context": context or {},
        })


class StubMasterAgent:
    def __init__(self, *, fail_process=False, fail_finalize=False):
        self.fail_process = fail_process
        self.fail_finalize = fail_finalize
        self.process_calls = 0
        self.log_filename = "stub.log"
        self.log_file_path = "stub.log"
        self.storage_agent = None

    async def process_all_events(self):
        self.process_calls += 1
        if self.fail_process:
            raise RuntimeError("processing error")

    def finalize_run_logs(self):
        if self.fail_finalize:
            raise ValueError("finalize error")


async def test_orchestrator_emits_alert_on_handled_exception():
    alert_agent = DummyAlertAgent()
    master_agent = StubMasterAgent(fail_finalize=True)
    orchestrator = WorkflowOrchestrator(
        alert_agent=alert_agent,
        master_agent=master_agent,
    )

    await orchestrator.run()

    assert len(alert_agent.calls) == 1
    call = alert_agent.calls[0]
    assert call["severity"] == AlertSeverity.WARNING
    assert call["context"]["handled"] is True
    assert call["context"]["phase"] == "finalize"


async def test_orchestrator_escalates_alert_on_repeated_failures():
    alert_agent = DummyAlertAgent()
    master_agent = StubMasterAgent(fail_process=True)
    orchestrator = WorkflowOrchestrator(
        alert_agent=alert_agent,
        master_agent=master_agent,
        failure_threshold=2,
    )

    await orchestrator.run()
    await orchestrator.run()

    assert len(alert_agent.calls) == 2
    first, second = alert_agent.calls
    assert first["severity"] == AlertSeverity.ERROR
    assert first["context"].get("failure_count") == 1

    assert second["severity"] == AlertSeverity.CRITICAL
    assert second["context"].get("failure_count") == 2
    assert second["context"].get("escalated") is True
    assert second["context"]["handled"] is False
