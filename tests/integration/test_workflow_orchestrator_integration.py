"""Integration tests covering orchestrator error handling and configuration."""

from __future__ import annotations

import importlib
import json
from pathlib import Path

import pytest

import agents.master_workflow_agent as master_module
import config.config as config_module
from agents.alert_agent import AlertSeverity
from agents.workflow_orchestrator import WorkflowOrchestrator


class DummyAlertAgent:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def send_alert(self, message, severity, context=None):
        self.calls.append(
            {
                "message": message,
                "severity": severity,
                "context": context or {},
            }
        )


class NoOpWatcher:
    def __init__(self, *args, **kwargs):
        self.started = False

    def start(self) -> bool:
        self.started = True
        return True

    def stop(self) -> None:  # pragma: no cover - no-op for tests
        self.started = False


@pytest.fixture(autouse=True)
def disable_real_watcher(monkeypatch):
    monkeypatch.setattr(master_module, "LlmConfigurationWatcher", NoOpWatcher)
    yield


def test_backend_failure_triggers_alert(
    monkeypatch, tmp_path: Path, stub_agent_registry
) -> None:
    monkeypatch.setenv("RUN_LOG_DIR", str(tmp_path / "runs"))
    monkeypatch.setenv("RESEARCH_ARTIFACT_DIR", str(tmp_path / "research" / "artifacts"))
    monkeypatch.setenv("SETTINGS_SKIP_DOTENV", "1")
    reloaded_config = importlib.reload(config_module)
    monkeypatch.setattr(master_module, "settings", reloaded_config.settings)

    master_agent = master_module.MasterWorkflowAgent()
    if hasattr(master_agent, "storage_agent"):
        master_agent.storage_agent.reset_failure_count("workflow_run")

    def fail_process():
        raise ConnectionError("CRM backend unavailable")

    monkeypatch.setattr(master_agent, "process_all_events", fail_process)

    alert_agent = DummyAlertAgent()
    orchestrator = WorkflowOrchestrator(
        alert_agent=alert_agent, master_agent=master_agent, failure_threshold=3
    )

    orchestrator.run()

    assert alert_agent.calls
    call = alert_agent.calls[-1]
    assert call["severity"] == AlertSeverity.CRITICAL
    assert call["context"]["handled"] is False
    assert call["context"]["exception_type"] == "ConnectionError"
    assert "escalated" not in call["context"]


def test_repeated_failures_escalate_to_critical(
    monkeypatch, tmp_path: Path, stub_agent_registry
):
    monkeypatch.setenv("RUN_LOG_DIR", str(tmp_path / "runs"))
    monkeypatch.setenv("RESEARCH_ARTIFACT_DIR", str(tmp_path / "research" / "artifacts"))
    monkeypatch.setenv("SETTINGS_SKIP_DOTENV", "1")
    reloaded_config = importlib.reload(config_module)
    monkeypatch.setattr(master_module, "settings", reloaded_config.settings)

    master_agent = master_module.MasterWorkflowAgent()
    if hasattr(master_agent, "storage_agent"):
        master_agent.storage_agent.reset_failure_count("workflow_run")

    def fail_process():
        raise RuntimeError("transient failure")

    monkeypatch.setattr(master_agent, "process_all_events", fail_process)

    alert_agent = DummyAlertAgent()
    orchestrator = WorkflowOrchestrator(
        alert_agent=alert_agent, master_agent=master_agent, failure_threshold=2
    )

    orchestrator.run()
    orchestrator.run()

    assert len(alert_agent.calls) == 2
    first, second = alert_agent.calls
    assert first["severity"] == AlertSeverity.ERROR
    assert first["context"].get("failure_count") == 1
    assert second["severity"] == AlertSeverity.CRITICAL
    assert second["context"].get("escalated") is True


def test_agent_swaps_can_be_driven_by_configuration(
    monkeypatch, tmp_path: Path, stub_agent_registry
):
    config_file = tmp_path / "agent_overrides.json"
    config_file.write_text(
        json.dumps(
            {
                "agents": {
                    "polling": "stub-polling",
                    "trigger": "stub-trigger",
                    "extraction": "stub-extraction",
                    "human": "stub-human",
                    "crm": "stub-crm",
                    "internal_research": "internal_research",
                    "dossier_research": "dossier_research",
                    "similar_companies": "similar_companies_level1",
                }
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setenv("AGENT_CONFIG_FILE", str(config_file))
    monkeypatch.setenv("SETTINGS_SKIP_DOTENV", "1")
    monkeypatch.setenv("RESEARCH_ARTIFACT_DIR", str(tmp_path / "research" / "artifacts"))
    reloaded_config = importlib.reload(config_module)
    monkeypatch.setattr(master_module, "settings", reloaded_config.settings)

    master_agent = master_module.MasterWorkflowAgent()

    assert isinstance(master_agent.event_agent, stub_agent_registry["polling"])
    assert isinstance(master_agent.trigger_agent, stub_agent_registry["trigger"])
    assert isinstance(master_agent.extraction_agent, stub_agent_registry["extraction"])
    assert isinstance(master_agent.human_agent, stub_agent_registry["human"])
    assert isinstance(master_agent.crm_agent, stub_agent_registry["crm"])
    assert isinstance(
        master_agent.internal_research_agent,
        stub_agent_registry["internal_research"],
    )
    assert isinstance(
        master_agent.dossier_research_agent,
        stub_agent_registry["dossier_research"],
    )
    assert isinstance(
        master_agent.similar_companies_agent,
        stub_agent_registry["similar_companies"],
    )
