"""
WorkflowOrchestrator: Central orchestrator for the Agentic Intelligence Research workflow.

- Controls the full workflow (polling, trigger detection, extraction, HITL, CRM, persistence).
- Handles logging, error handling, status, and retries.
- Calls the MasterWorkflowAgent and sub-agents as pure logic modules.
"""

import logging
from typing import Dict, Optional

from agents.alert_agent import AlertAgent, AlertSeverity
from agents.master_workflow_agent import MasterWorkflowAgent

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
        logger.info("Workflow orchestrator started.")

        if self._init_error is not None:
            logger.warning(
                "Workflow orchestrator initialisation skipped due to configuration error."
            )
            return

        try:
            self.master_agent.process_all_events()
        except Exception as exc:
            logger.exception("Workflow failed with exception:")
            self._handle_exception(
                exc,
                handled=False,
                context={"phase": "run"},
                track_failure=True,
            )
        else:
            logger.info("Workflow completed successfully.")
            self._reset_failure_count(self._failure_key)
        finally:
            self._finalize()

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
