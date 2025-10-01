"""
Entrypoint for the Agentic Intelligence Research workflow.

# Notes:
# - This script initializes and starts the WorkflowOrchestrator, which orchestrates the entire polling and event-processing workflow.
# - All orchestration, error handling, and logging is now handled in WorkflowOrchestrator.
"""

import asyncio

from dotenv import load_dotenv


async def _async_main() -> None:
    load_dotenv()

    import logging
    from agents.workflow_orchestrator import WorkflowOrchestrator

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s [run_id=%(run_id)s] %(message)s",
    )

    orchestrator = WorkflowOrchestrator()
    orchestrator.install_signal_handlers(asyncio.get_running_loop())
    try:
        await orchestrator.run()
    finally:
        await orchestrator.shutdown()


def main() -> None:
    asyncio.run(_async_main())


if __name__ == "__main__":
    main()
