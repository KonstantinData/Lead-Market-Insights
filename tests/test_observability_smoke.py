from __future__ import annotations

from typing import Any, Dict, Iterable

import pytest

pytest.importorskip("opentelemetry")
pytest.importorskip("opentelemetry.sdk.metrics.export")
pytest.importorskip("opentelemetry.sdk.trace.export")

from opentelemetry.sdk.metrics.export import InMemoryMetricReader
from opentelemetry.sdk.trace.export import InMemorySpanExporter, SimpleSpanProcessor

from agents.master_workflow_agent import MasterWorkflowAgent
from agents.workflow_orchestrator import WorkflowOrchestrator
from config.config import settings
from utils import observability


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


class DummyHumanAgent:
    def request_dossier_confirmation(
        self, _event: Dict[str, Any], _info: Dict[str, Any]
    ) -> Dict[str, Any]:
        return {
            "dossier_required": True,
            "details": {"note": "prepare dossier"},
            "audit_id": "audit-dossier",
        }

    def request_info(
        self, _event: Dict[str, Any], extracted: Dict[str, Any]
    ) -> Dict[str, Any]:
        extracted.setdefault("info", {})
        extracted["info"]["company_name"] = "Example Corp"
        extracted["info"]["web_domain"] = "example.com"
        extracted["is_complete"] = True
        extracted["audit_id"] = "audit-info"
        return extracted


class DummyCrmAgent:
    def __init__(self) -> None:
        self.sent: list[Dict[str, Any]] = []

    def send(self, event: Dict[str, Any], info: Dict[str, Any]) -> None:
        self.sent.append({"event": event, "info": info})


def _find_metric(metrics_data, name: str):
    for resource_metrics in metrics_data.resource_metrics:
        for scope_metrics in resource_metrics.scope_metrics:
            for metric in scope_metrics.metrics:
                if metric.name == name:
                    return metric
    raise AssertionError(f"Metric {name} not found")


def _collect_sum_points(metric) -> Dict[frozenset, float]:
    points = {}
    for point in metric.data.data_points:
        points[frozenset(point.attributes.items())] = point.value
    return points


def _collect_histogram_operations(metric) -> set[str]:
    operations = set()
    for point in metric.data.data_points:
        attrs = dict(point.attributes)
        operations.add(attrs.get("operation"))
    return operations


def test_observability_records_metrics_and_traces(monkeypatch, tmp_path):
    monkeypatch.setenv("SETTINGS_SKIP_DOTENV", "1")
    metric_reader = InMemoryMetricReader()
    span_exporter = InMemorySpanExporter()
    span_processor = SimpleSpanProcessor(span_exporter)
    observability.configure_observability(
        metric_reader=metric_reader,
        span_processor=span_processor,
        force=True,
    )

    monkeypatch.setattr(
        "config.watcher.LlmConfigurationWatcher.start", lambda self: False
    )

    original_run_dir = settings.run_log_dir
    try:
        settings.run_log_dir = tmp_path / "runs"
        settings.run_log_dir.mkdir(parents=True, exist_ok=True)

        event = {
            "id": "evt-1",
            "summary": "Soft trigger event",
            "organizer": {"email": "user@example.com"},
        }
        extraction_payload = {
            "info": {"company_name": None, "web_domain": ""},
            "is_complete": False,
        }

        crm_agent = DummyCrmAgent()
        orchestrator = WorkflowOrchestrator(
            master_agent=MasterWorkflowAgent(
                event_agent=DummyEventAgent([event]),
                trigger_agent=DummyTriggerAgent(
                    {
                        "trigger": True,
                        "type": "soft",
                        "matched_word": "briefing",
                        "matched_field": "summary",
                    }
                ),
                extraction_agent=DummyExtractionAgent(extraction_payload),
                human_agent=DummyHumanAgent(),
                crm_agent=crm_agent,
            )
        )

        orchestrator.run()

        assert crm_agent.sent, "CRM agent should have been invoked"

        log_contents = orchestrator.master_agent.log_file_path.read_text(
            encoding="utf-8"
        )
        assert orchestrator._last_run_id in log_contents

        metrics_data = metric_reader.get_metrics_data()
        run_metric = _find_metric(metrics_data, "workflow_runs_total")
        run_points = _collect_sum_points(run_metric)
        assert run_points[frozenset({("status", "success")})] == 1

        trigger_metric = _find_metric(metrics_data, "workflow_trigger_matches_total")
        trigger_points = _collect_sum_points(trigger_metric)
        assert trigger_points[frozenset({("trigger.type", "soft")})] == 1

        hitl_metric = _find_metric(metrics_data, "workflow_hitl_outcomes_total")
        hitl_points = _collect_sum_points(hitl_metric)
        assert (
            hitl_points[
                frozenset({("hitl.kind", "dossier"), ("hitl.outcome", "approved")})
            ]
            == 1
        )
        assert (
            hitl_points[
                frozenset({("hitl.kind", "missing_info"), ("hitl.outcome", "completed")})
            ]
            == 1
        )

        latency_metric = _find_metric(
            metrics_data, "workflow_operation_duration_ms"
        )
        operations = _collect_histogram_operations(latency_metric)
        assert {"run", "trigger_detection", "extraction", "hitl_dossier", "hitl_missing_info", "crm_dispatch"}.issubset(
            operations
        )

        finished_spans = span_exporter.get_finished_spans()
        assert finished_spans, "Expected spans to be exported"
        trace_ids = {span.context.trace_id for span in finished_spans}
        assert len(trace_ids) == 1

        run_span = next(span for span in finished_spans if span.name == "workflow.run")
        assert run_span.attributes["workflow.run_id"] == orchestrator._last_run_id

        child_spans = [span for span in finished_spans if span is not run_span]
        assert child_spans, "Expected child spans for operations"
        for span in child_spans:
            assert span.parent is not None
            assert span.parent.span_id == run_span.context.span_id
            assert span.attributes.get("workflow.run_id") == orchestrator._last_run_id
    finally:
        settings.run_log_dir = original_run_dir
