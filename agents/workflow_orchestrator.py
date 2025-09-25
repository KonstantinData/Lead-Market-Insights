"""
WorkflowOrchestrator: Central orchestrator for the Agentic Intelligence Research workflow.

- Controls the full workflow (polling, trigger detection, extraction, HITL, CRM, S3 upload).
- Handles logging, error handling, status, and retries.
- Calls the MasterWorkflowAgent and sub-agents as pure logic modules.
"""

from agents.master_workflow_agent import MasterWorkflowAgent
import logging
from typing import Optional

logger = logging.getLogger("WorkflowOrchestrator")


class WorkflowOrchestrator:
    def __init__(self):
        # Initialize the logic agent
        self._init_error: Optional[Exception] = None
        try:
            self.master_agent = MasterWorkflowAgent()
            self.log_filename = self.master_agent.log_filename
        except EnvironmentError as exc:
            # Missing environment configuration is expected in test environments.
            logger.error("Failed to initialise MasterWorkflowAgent: %s", exc)
            self.master_agent = None
            self.log_filename = "polling_trigger.log"
            self._init_error = exc

    def run(self):
        logger.info("Workflow orchestrator started.")

        if self._init_error is not None:
            logger.warning(
                "Workflow orchestrator initialisation skipped due to configuration error."
            )
            return

        try:
            self.master_agent.process_all_events()
            logger.info("Workflow completed successfully.")
        except Exception:
            logger.exception("Workflow failed with exception:")
        finally:
            self._finalize()

    def _finalize(self):
        # Optional: Upload log file to S3, etc.
        if not self.master_agent:
            return

        try:
            self.master_agent.upload_log_to_s3()
        except Exception:
            logger.error("Failed to upload log file to S3", exc_info=True)

        logger.info("Orchestration finalized.")
