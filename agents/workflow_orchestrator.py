"""
WorkflowOrchestrator: Central orchestrator for the Agentic Intelligence Research workflow.

- Controls the full workflow (polling, trigger detection, extraction, HITL, CRM, persistence).
- Handles logging, error handling, status, and retries.
- Calls the MasterWorkflowAgent and sub-agents as pure logic modules.
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict, Mapping, Optional, Sequence, Union

from agents.alert_agent import AlertAgent, AlertSeverity
from agents.master_workflow_agent import MasterWorkflowAgent
from config.config import settings
from utils.observability import configure_observability, generate_run_id, workflow_run
from utils.reporting import convert_research_artifacts_to_pdfs

logger = logging.getLogger("WorkflowOrchestrator")


class WorkflowOrchestrator:
    def __init__(
        self,
        communication_backend=None,
        *,
        alert_agent: Optional[AlertAgent] = None,
        master_agent: Optional[MasterWorkflowAgent] = None,
        failure_threshold: int = 3,
    ):
        # Track init errors so run() can short-circuit gracefully.
        self._init_error: Optional[Exception] = None
        self.alert_agent = alert_agent
        self.failure_threshold = max(1, failure_threshold)
        self._failure_key = "workflow_run"
        self._failure_counts: Dict[str, int] = {}
        self._last_run_id: Optional[str] = None
        self._research_summary_root = Path(settings.research_artifact_dir) / "workflow_runs"

        configure_observability()

        try:
            # Support passing through the communication backend.
            self.master_agent = master_agent or MasterWorkflowAgent(
                communication_backend=communication_backend
            )
            self.log_filename = self.master_agent.log_filename
            self.storage_agent = getattr(self.master_agent, "storage_agent", None)
        except EnvironmentError as exc:
            # Missing env/config is expected in some (e.g., test) environments.
            logger.error("Failed to initialise MasterWorkflowAgent: %s", exc)
            self.master_agent = None
            self.log_filename = "polling_trigger.log"
            self._init_error = exc
            self.storage_agent = None
            self._handle_exception(exc, handled=True, context={"phase": "initialisation"})

    def run(self):
        run_id = generate_run_id()
        with workflow_run(run_id=run_id) as run_context:
            self._last_run_id = run_context.run_id
            logger.info("Workflow orchestrator started.")

            if self._init_error is not None:
                logger.warning(
                    "Workflow orchestrator initialisation skipped due to configuration error."
                )
                run_context.mark_status("skipped")
                return

            try:
                if self.master_agent:
                    if hasattr(self.master_agent, "initialize_run"):
                        self.master_agent.initialize_run(run_context.run_id)
                    results = self.master_agent.process_all_events() or []
                    self._report_research_errors(run_context.run_id, results)
                    try:
                        self._store_research_outputs(run_context.run_id, results)
                    except Exception as exc:  # pragma: no cover - defensive guard
                        logger.error(
                            "Failed to persist research outputs", exc_info=True
                        )
                        self._handle_exception(
                            exc,
                            handled=True,
                            context={
                                "phase": "store_research",
                                "run_id": run_context.run_id,
                            },
                        )
            except Exception as exc:
                run_context.mark_failure(exc)
                logger.exception("Workflow failed with exception:")
                self._handle_exception(
                    exc,
                    handled=False,
                    context={"phase": "run"},
                    track_failure=True,
                )
            else:
                run_context.mark_success()
                logger.info("Workflow completed successfully.")
                self._reset_failure_count(self._failure_key)
            finally:
                self._finalize()

    def _store_research_outputs(
        self, run_id: str, results: Sequence[Dict[str, object]]
    ) -> None:
        if not results:
            return

        summary_dir = self._research_summary_root / run_id
        summary_dir.mkdir(parents=True, exist_ok=True)
        summary_path = summary_dir / "summary.json"

        sanitized: list[Dict[str, object]] = []
        for entry in results:
            sanitized_entry = {
                "event_id": entry.get("event_id"),
                "status": entry.get("status"),
                "crm_dispatched": entry.get("crm_dispatched", False),
                "trigger": entry.get("trigger"),
                "extraction": entry.get("extraction"),
                "research": entry.get("research"),
                "research_errors": entry.get("research_errors", []),
            }

            pdf_artifacts = self._generate_pdf_artifacts(run_id, entry)
            if pdf_artifacts:
                sanitized_entry["pdf_artifacts"] = pdf_artifacts

            sanitized.append(sanitized_entry)

        summary_path.write_text(
            json.dumps(sanitized, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        logger.info(
            "Stored research summary for run %s at %s",
            run_id,
            summary_path.as_posix(),
        )

    def _generate_pdf_artifacts(
        self, run_id: str, result_entry: Mapping[str, object]
    ) -> Optional[Dict[str, str]]:
        research_section = result_entry.get("research")
        if not isinstance(research_section, Mapping):
            return None

        dossier = research_section.get("dossier_research")
        similar = research_section.get("similar_companies_level1")
        if not isinstance(dossier, Mapping) or not isinstance(similar, Mapping):
            return None

        dossier_source = self._resolve_pdf_source(dossier)
        similar_source = self._resolve_pdf_source(similar)
        if dossier_source is None or similar_source is None:
            return None

        output_dir = Path(settings.research_pdf_dir) / run_id
        event_id = result_entry.get("event_id")

        try:
            return convert_research_artifacts_to_pdfs(
                dossier_source, similar_source, output_dir=output_dir
            )
        except ImportError as exc:
            logger.warning(
                "Skipping PDF generation for event %s due to missing dependency: %s",
                event_id,
                exc,
            )
        except Exception:
            logger.exception(
                "Failed to generate PDF artefacts for event %s", event_id
            )
        return None

    @staticmethod
    def _resolve_pdf_source(
        research_result: Mapping[str, object]
    ) -> Optional[Union[str, Path, Mapping[str, Any]]]:
        payload = research_result.get("payload")
        if isinstance(payload, Mapping):
            return payload

        artifact_path = research_result.get("artifact_path")
        if isinstance(artifact_path, str) and artifact_path:
            return artifact_path

        if isinstance(payload, Mapping):  # pragma: no cover - defensive double check
            nested_path = payload.get("artifact_path")
            if isinstance(nested_path, str) and nested_path:
                return nested_path

        return None

    def _report_research_errors(
        self, run_id: str, results: Sequence[Dict[str, object]]
    ) -> None:
        if not results:
            return

        for entry in results:
            for error in entry.get("research_errors", []) or []:
                message = (
                    f"Research agent '{error.get('agent')}' failed during run {run_id}."
                )
                context = {
                    "run_id": run_id,
                    "event_id": entry.get("event_id"),
                    "agent": error.get("agent"),
                    "error": error.get("error"),
                }
                self._emit_alert(message, AlertSeverity.ERROR, context)

    def _finalize(self):
        if not self.master_agent:
            return

        try:
            self.master_agent.finalize_run_logs()
            logger.info(
                "Run log stored locally at %s", self.master_agent.log_file_path
            )
        except Exception as exc:
            logger.error("Failed to finalise local log storage", exc_info=True)
            self._handle_exception(
                exc,
                handled=True,
                context={"phase": "finalize"},
            )

        logger.info("Orchestration finalized.")

    # ------------------------------------------------------------------
    # Alert helpers
    # ------------------------------------------------------------------
    def _handle_exception(
        self,
        exc: Exception,
        *,
        handled: bool,
        context: Optional[Dict[str, object]] = None,
        track_failure: bool = False,
    ) -> None:
        severity = self._map_exception_to_severity(exc)
        ctx: Dict[str, object] = {
            "exception_type": type(exc).__name__,
            "handled": handled,
        }
        if context:
            ctx.update(context)

        if track_failure:
            failure_count = self._increment_failure_count(self._failure_key)
            ctx["failure_count"] = failure_count
            if failure_count >= self.failure_threshold:
                severity = AlertSeverity.CRITICAL
                ctx["escalated"] = True

        message = (
            "Handled" if handled else "Unhandled"
        ) + f" exception in WorkflowOrchestrator: {exc}"
        self._emit_alert(message, severity, ctx)

    def _emit_alert(
        self, message: str, severity: AlertSeverity, context: Dict[str, object]
    ) -> None:
        if not self.alert_agent:
            return

        self.alert_agent.send_alert(message, severity, context=context)

    def _map_exception_to_severity(self, exc: Exception) -> AlertSeverity:
        if isinstance(exc, (EnvironmentError, OSError)):
            return AlertSeverity.CRITICAL
        if isinstance(exc, (RuntimeError, ConnectionError, TimeoutError)):
            return AlertSeverity.ERROR
        if isinstance(exc, (ValueError, KeyError)):
            return AlertSeverity.WARNING
        return AlertSeverity.ERROR

    def _increment_failure_count(self, key: str) -> int:
        if self.storage_agent and hasattr(self.storage_agent, "increment_failure_count"):
            return self.storage_agent.increment_failure_count(key)

        self._failure_counts[key] = self._failure_counts.get(key, 0) + 1
        return self._failure_counts[key]

    def _reset_failure_count(self, key: str) -> None:
        if self.storage_agent and hasattr(self.storage_agent, "reset_failure_count"):
            self.storage_agent.reset_failure_count(key)
        elif key in self._failure_counts:
            del self._failure_counts[key]
