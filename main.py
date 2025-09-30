"""
Entrypoint for the Agentic Intelligence Research workflow.

# Notes:
# - This script initializes and starts the WorkflowOrchestrator, which orchestrates the entire polling and event-processing workflow.
# - All orchestration, error handling, and logging is now handled in WorkflowOrchestrator.
"""

import asyncio

from dotenv import load_dotenv


async def main() -> None:
    load_dotenv()

    import logging
    from agents.workflow_orchestrator import WorkflowOrchestrator

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s [run_id=%(run_id)s] %(message)s",
    )

    orchestrator = WorkflowOrchestrator()
    orchestrator.run()


if __name__ == "__main__":
    asyncio.run(main())
