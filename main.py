"""
Entrypoint for the Agentic Intelligence Research workflow.

# Notes:
# - This script initializes and starts the MasterWorkflowAgent, which orchestrates the entire polling and event-processing workflow.
# - All business logic is encapsulated in the MasterWorkflowAgent.
"""

import logging
from agents.master_workflow_agent import MasterWorkflowAgent

if __name__ == "__main__":
    # Set up logging (optional: customize as needed)
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s"
    )

    agent = MasterWorkflowAgent()
    agent.run_workflow()
