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

from utils.observability import get_current_run_id

# Optional / graceful telemetry setup (new)
try:
    from utils.telemetry import setup_telemetry
except ImportError:  # telemetry module not yet present
    setup_telemetry = None  # type: ignore


class _RunIdLoggingFilter(logging.Filter):
    """Ensure log records always include a run identifier."""

    def filter(self, record: logging.LogRecord) -> bool:  # noqa: D401 - standard logging API
        if getattr(record, "run_id", None) in {None, ""}:
            record.run_id = get_current_run_id() or "n/a"
        return True


_run_id_filter = _RunIdLoggingFilter()
_run_id_filter_attached = False


def _init_logging() -> None:
    # Avoid re-configuring if already set (e.g. tests or embedding)
    global _run_id_filter_attached

    root_logger = logging.getLogger()
    if not _run_id_filter_attached:
        root_logger.addFilter(_run_id_filter)
        _run_id_filter_attached = True

    for handler in root_logger.handlers:
        if _run_id_filter not in handler.filters:
            handler.addFilter(_run_id_filter)

    if root_logger.handlers:
        return
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s [run_id=%(run_id)s] %(message)s",
    )

    for handler in logging.getLogger().handlers:
        if _run_id_filter not in handler.filters:
            handler.addFilter(_run_id_filter)


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
