"""
Entrypoint for the Agentic Intelligence Research workflow.

Responsibilities:
- Load environment (.env) early.
- Initialize structured logging (adds a run_id to every log line).
- Optionally initialize OpenTelemetry tracing (if enabled).
- Start and run the WorkflowOrchestrator event loop.
- Gracefully handle shutdown and signal registration.

Telemetry activation (tracing only):
Set:
  ENABLE_OTEL=true
and define:
  OTEL_EXPORTER_OTLP_ENDPOINT (e.g. http://otel-collector:4318)
You can also forcibly suppress telemetry during local dev with:
  OTEL_DISABLE_DEV=true

If telemetry is not enabled or misconfigured, the app continues without it.
"""

from __future__ import annotations

import asyncio
import logging
import os
from typing import Iterable

from dotenv import load_dotenv

from utils.observability import get_current_run_id

# Try to import optional telemetry setup (added via utils/telemetry.py)
try:
    from utils.telemetry import setup_telemetry
except ImportError:  # Module not present yet
    setup_telemetry = None  # type: ignore[attr-defined]


class _RunIdLoggingFilter(logging.Filter):
    """Logging filter ensuring every record has a run_id attribute."""

    def filter(self, record: logging.LogRecord) -> bool:  # noqa: D401
        if getattr(record, "run_id", None) in {None, ""}:
            record.run_id = get_current_run_id() or "n/a"
        return True


_run_id_filter = _RunIdLoggingFilter()
_run_id_filter_attached = False


def _attach_filter_to_handlers(handlers: Iterable[logging.Handler]) -> None:
    for handler in handlers:
        if _run_id_filter not in handler.filters:
            handler.addFilter(_run_id_filter)


def _init_logging() -> None:
    """
    Initialize root logging with a consistent format including run_id.
    Safe to call multiple times (idempotent).
    """
    global _run_id_filter_attached

    root_logger = logging.getLogger()

    if not _run_id_filter_attached:
        root_logger.addFilter(_run_id_filter)
        _run_id_filter_attached = True

    # If handlers already exist (e.g., tests), just ensure filter is added.
    if root_logger.handlers:
        _attach_filter_to_handlers(root_logger.handlers)
        return

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s [run_id=%(run_id)s] %(message)s",
    )
    _attach_filter_to_handlers(logging.getLogger().handlers)


def _telemetry_should_run() -> bool:
    """
    Decide whether telemetry should initialize.

    Rules:
    - If OTEL_DISABLE_DEV is truthy -> skip.
    - If setup_telemetry is not available -> skip.
    - If ENABLE_OTEL is truthy AND OTEL_EXPORTER_OTLP_ENDPOINT is set -> run.
      (ENABLE_OTEL checks explicit intent; endpoint ensures a destination.)
    """
    if setup_telemetry is None:
        return False

    disable_val = os.getenv("OTEL_DISABLE_DEV", "").lower()
    if disable_val in {"1", "true", "yes", "on"}:
        return False

    enable_val = os.getenv("ENABLE_OTEL", "").lower()
    if enable_val not in {"1", "true", "yes", "on"}:
        return False

    if not os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT"):
        logging.getLogger(__name__).info(
            "Telemetry requested (ENABLE_OTEL set) but OTEL_EXPORTER_OTLP_ENDPOINT is missing; skipping."
        )
        return False

    return True


async def _async_main() -> None:
    # Load environment variables from .env (if present) before other setup.
    load_dotenv()

    # Structured logging with run_id injection.
    _init_logging()

    # Optional telemetry (tracing).
    if _telemetry_should_run():
        try:
            setup_telemetry(service_name="lead-market-insights")  # type: ignore[misc]
        except Exception:
            logging.getLogger(__name__).warning(
                "Telemetry setup failed; continuing without instrumentation.",
                exc_info=True,
            )
    else:
        logging.getLogger(__name__).info(
            "Telemetry not enabled (expected in some environments)."
        )

    # Delayed import: components that may rely on env/logging initialization.
    from agents.workflow_orchestrator import WorkflowOrchestrator  # noqa: WPS433

    orchestrator = WorkflowOrchestrator()

    # Install signal handlers (may not work on all platforms, e.g. Windows under some shells).
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
    """Synchronous entry — wraps the async workflow."""
    asyncio.run(_async_main())


if __name__ == "__main__":
    main()
