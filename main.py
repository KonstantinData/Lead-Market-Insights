"""
Entrypoint for the Agentic Intelligence Research workflow.

Notes:
- Initializes and starts the WorkflowOrchestrator which manages polling and event-processing.
- Logging, error handling and shutdown are coordinated centrally in the orchestrator.
"""

import asyncio
import logging
import os

from dotenv import load_dotenv

# Optional / graceful telemetry setup (new)
try:
    from utils.telemetry import setup_telemetry
except ImportError:  # telemetry module not yet present
    setup_telemetry = None  # type: ignore


def _init_logging() -> None:
    # Avoid re-configuring if already set (e.g. tests or embedding)
    if logging.getLogger().handlers:
        return
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s [run_id=%(run_id)s] %(message)s",
    )


async def _async_main() -> None:
    load_dotenv()

    _init_logging()

    # Telemetry only if module available and not disabled
    if setup_telemetry and os.environ.get("OTEL_DISABLE_DEV", "").lower() not in {
        "1",
        "true",
        "yes",
    }:
        try:
            setup_telemetry(service_name="lead-market-insights")
        except Exception:  # pragma: no cover – hardening
            logging.getLogger(__name__).warning(
                "Telemetry setup failed; continuing without instrumentation.",
                exc_info=True,
            )

    from agents.workflow_orchestrator import (
        WorkflowOrchestrator,
    )  # local import after env load

    orchestrator = WorkflowOrchestrator()
    # Signal handler install (may be skipped on restricted platforms)
    try:
        orchestrator.install_signal_handlers(asyncio.get_running_loop())
    except NotImplementedError:
        logging.getLogger(__name__).warning(
            "Signal handlers not supported on this platform; continuing without them."
        )

    try:
        await orchestrator.run()
    finally:
        await orchestrator.shutdown()


def main() -> None:
    asyncio.run(_async_main())


if __name__ == "__main__":
    main()
