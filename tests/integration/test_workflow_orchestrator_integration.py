"""Integration tests covering orchestrator error handling and configuration."""

from __future__ import annotations

import json
from pathlib import Path
from typing import List

import pytest

import agents.master_workflow_agent as master_module
import agents.workflow_orchestrator as workflow_orchestrator
from agents.alert_agent import AlertSeverity
from agents.workflow_orchestrator import WorkflowOrchestrator
from utils.observability import current_run_id_var, generate_run_id


pytestmark = pytest.mark.asyncio


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


class RecordingMasterAgent:
    """Minimal master agent stub that records orchestration lifecycle calls."""

    def __init__(self, *, log_dir: Path, results: List[dict[str, object]]):
        self.log_filename = "master.log"
        self.log_file_path = log_dir / self.log_filename
        self.log_file_path.write_text("", encoding="utf-8")
        self.results = results
        self.initialized_runs: list[str] = []
        self.finalize_called = False
        self.storage_agent = None
        self.workflow_log_manager = None

    def attach_run(self, run_id: str, *_args, **_kwargs) -> None:
        self.initialized_runs.append(run_id)

    async def process_all_events(self) -> List[dict[str, object]]:
        return list(self.results)

    def finalize_run_logs(self) -> None:
        self.finalize_called = True


@pytest.fixture(autouse=True)
def disable_real_watcher(monkeypatch):
    monkeypatch.setattr(master_module, "LlmConfigurationWatcher", NoOpWatcher)
    yield


async def test_backend_failure_triggers_alert(
    monkeypatch, orchestrator_environment, stub_agent_registry
) -> None:
    master_agent = master_module.MasterWorkflowAgent()
    if hasattr(master_agent, "storage_agent"):
        master_agent.storage_agent.reset_failure_count("workflow_run")

    async def fail_process():
        raise ConnectionError("CRM backend unavailable")

    monkeypatch.setattr(master_agent, "process_all_events", fail_process)

    alert_agent = DummyAlertAgent()
    run_id = generate_run_id()
    token = current_run_id_var.set(run_id)
    orchestrator = WorkflowOrchestrator(
        alert_agent=alert_agent,
        master_agent=master_agent,
        failure_threshold=3,
        run_id=run_id,
    )

    try:
        await orchestrator.run()
    finally:
        await orchestrator.shutdown()
        current_run_id_var.reset(token)

    assert alert_agent.calls
    call = alert_agent.calls[-1]
    assert call["severity"] == AlertSeverity.CRITICAL
    assert call["context"]["handled"] is False
    assert call["context"]["exception_type"] == "ConnectionError"
    assert "escalated" not in call["context"]


async def test_repeated_failures_escalate_to_critical(
    monkeypatch, orchestrator_environment, stub_agent_registry
):
    master_agent = master_module.MasterWorkflowAgent()
    if hasattr(master_agent, "storage_agent"):
        master_agent.storage_agent.reset_failure_count("workflow_run")

    async def fail_process():
        raise RuntimeError("transient failure")

    monkeypatch.setattr(master_agent, "process_all_events", fail_process)

    alert_agent = DummyAlertAgent()
    run_id = generate_run_id()
    token = current_run_id_var.set(run_id)
    orchestrator = WorkflowOrchestrator(
        alert_agent=alert_agent,
        master_agent=master_agent,
        failure_threshold=2,
        run_id=run_id,
    )

    try:
        await orchestrator.run()
        await orchestrator.run()
    finally:
        await orchestrator.shutdown()
        current_run_id_var.reset(token)

    assert len(alert_agent.calls) == 2
    first, second = alert_agent.calls
    assert first["severity"] == AlertSeverity.ERROR
    assert first["context"].get("failure_count") == 1
    assert second["severity"] == AlertSeverity.CRITICAL
    assert second["context"].get("escalated") is True


async def test_agent_swaps_can_be_driven_by_configuration(
    monkeypatch, tmp_path: Path, orchestrator_environment, stub_agent_registry
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


async def test_orchestrator_records_research_artifacts_and_email_details(
    monkeypatch, tmp_path: Path, orchestrator_environment
) -> None:
    summary_root = orchestrator_environment["artifact_dir"]

    generated_calls = []

    def fake_convert(dossier, similar, *, output_dir):
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        dossier_path = output_dir / "dossier_research.pdf"
        similar_path = output_dir / "similar_companies.pdf"
        dossier_path.write_text("pdf", encoding="utf-8")
        similar_path.write_text("pdf", encoding="utf-8")
        generated_calls.append((dossier, similar, output_dir))
        return {
            "dossier_pdf": dossier_path.as_posix(),
            "similar_companies_pdf": similar_path.as_posix(),
        }

    monkeypatch.setattr(
        workflow_orchestrator,
        "convert_research_artifacts_to_pdfs",
        fake_convert,
    )

    snapshot_dir = Path(__file__).resolve().parents[1] / "unit" / "snapshots"
    dossier_snapshot = json.loads(
        (snapshot_dir / "company_detail_research.json").read_text(encoding="utf-8")
    )
    similar_snapshot = json.loads(
        (snapshot_dir / "similar_companies_level1.json").read_text(encoding="utf-8")
    )

    research_results = [
        {
            "event_id": "evt-456",
            "status": "dispatched_to_crm",
            "crm_dispatched": True,
            "trigger": {"type": "soft", "confidence": 0.96},
            "extraction": {
                "info": {
                    "company_name": "Example Corp",
                    "web_domain": "example.ai",
                },
                "is_complete": True,
            },
            "research": {
                "internal_research": {
                    "agent": "internal_research",
                    "status": "REPORT_REQUIRED",
                    "payload": {
                        "action": "REPORT_REQUIRED",
                        "existing_report": False,
                        "artifacts": {
                            "neighbor_samples": "stub/level1_samples.json",
                            "crm_match": "stub/crm_matching_company.json",
                        },
                    },
                },
                "dossier_research": {
                    "agent": "dossier_research",
                    "status": "completed",
                    "artifact_path": "stub/evt-456_company_detail_research.json",
                    "payload": dossier_snapshot,
                },
                "similar_companies_level1": {
                    "agent": "similar_companies_level1",
                    "status": "completed",
                    "payload": {
                        "company_name": similar_snapshot["company_name"],
                        "run_id": similar_snapshot["run_id"],
                        "event_id": similar_snapshot["event_id"],
                        "results": similar_snapshot["results"],
                        "artifact_path": (
                            "stub/similar_companies_level1/"
                            "run-123/similar_companies_level1_evt-456.json"
                        ),
                    },
                },
            },
            "research_errors": [],
            "final_email": {
                "subject": "Research ready",
                "attachments": ["stub/dossier.pdf"],
                "links": ["https://crm.example.com/attachments/run-123"],
            },
        }
    ]

    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    master_agent = RecordingMasterAgent(log_dir=log_dir, results=research_results)

    run_id = generate_run_id()
    token = current_run_id_var.set(run_id)
    orchestrator = WorkflowOrchestrator(master_agent=master_agent, run_id=run_id)
    try:
        await orchestrator.run()
    finally:
        await orchestrator.shutdown()
        current_run_id_var.reset(token)

    assert master_agent.initialized_runs == [run_id]
    assert master_agent.finalize_called is True

    summary_path = summary_root / "workflow_runs" / run_id / "summary.json"
    assert summary_path.exists()

    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    assert len(summary) == 1
    entry = summary[0]
    assert entry["event_id"] == "evt-456"
    assert entry["crm_dispatched"] is True
    assert set(entry["research"].keys()) == {
        "internal_research",
        "dossier_research",
        "similar_companies_level1",
    }

    internal_payload = entry["research"]["internal_research"]["payload"]
    assert internal_payload["action"] == "REPORT_REQUIRED"
    assert (
        internal_payload["artifacts"]["crm_match"] == "stub/crm_matching_company.json"
    )

    dossier_payload = entry["research"]["dossier_research"]["payload"]
    assert dossier_payload["report_type"] == "Company Detail Research"
    assert dossier_payload["company"]["name"] == "Example Corp"

    similar_payload = entry["research"]["similar_companies_level1"]["payload"]
    assert len(similar_payload["results"]) == 2
    assert [result["id"] for result in similar_payload["results"]] == ["2", "3"]
    artifact_path = similar_payload["artifact_path"]
    assert artifact_path.endswith("similar_companies_level1_evt-456.json")
    assert "/run-123/" in artifact_path.replace("\\", "/")

    final_email = master_agent.results[0]["final_email"]
    assert final_email["attachments"] == ["stub/dossier.pdf"]
    assert final_email["links"][0].startswith("https://")

    assert generated_calls
    dossier_arg, similar_arg, output_dir = generated_calls[0]
    assert dossier_arg == dossier_snapshot
    assert similar_arg["results"] == similar_snapshot["results"]
    assert output_dir == Path(workflow_orchestrator.settings.research_pdf_dir) / run_id

    pdf_artifacts = entry.get("pdf_artifacts")
    assert pdf_artifacts
    dossier_pdf = Path(pdf_artifacts["dossier_pdf"])
    similar_pdf = Path(pdf_artifacts["similar_companies_pdf"])
    assert dossier_pdf.exists()
    assert similar_pdf.exists()
