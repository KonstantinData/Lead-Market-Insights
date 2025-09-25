"""
WorkflowOrchestrator: Central orchestrator for the Agentic Intelligence Research workflow.

- Controls the full workflow (polling, trigger detection, extraction, HITL, CRM, S3 upload).
- Handles logging, error handling, status, and retries.
- Calls the MasterWorkflowAgent and sub-agents as pure logic modules.
"""

from agents.master_workflow_agent import MasterWorkflowAgent
import logging

logger = logging.getLogger("WorkflowOrchestrator")


class WorkflowOrchestrator:
    def __init__(self):
        # Initialize the logic agent
        self.master_agent = MasterWorkflowAgent()
        self.log_filename = self.master_agent.log_filename

    def run(self):
        logger.info("Workflow orchestrator started.")

        try:
            self.master_agent.process_all_events()
            logger.info("Workflow completed successfully.")
        except Exception:
            logger.exception("Workflow failed with exception:")
        finally:
            self._finalize()

    def _finalize(self):
        # Optional: Upload log file to S3, etc.
        try:
            self.master_agent.upload_log_to_s3()
        except Exception:
            logger.error("Failed to upload log file to S3", exc_info=True)

        logger.info("Orchestration finalized.")
