"""
Entrypoint for the Agentic Intelligence Research workflow.

# Notes:
# - This script initializes and starts the WorkflowOrchestrator, which orchestrates the entire polling and event-processing workflow.
# - All orchestration, error handling, and logging is now handled in WorkflowOrchestrator.
"""

from dotenv import load_dotenv

load_dotenv()

import logging
from agents.workflow_orchestrator import WorkflowOrchestrator

if __name__ == "__main__":
    # Set up logging (optional: customize as needed)
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s"
    )

    orchestrator = WorkflowOrchestrator()
    orchestrator.run()
