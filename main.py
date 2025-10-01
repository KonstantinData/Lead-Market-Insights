import asyncio
import logging
import os
from dotenv import load_dotenv

from utils.observability import get_current_run_id

try:
    from utils.telemetry import setup_telemetry
except ImportError:
    setup_telemetry = None  # type: ignore

# NEW: env validation + compatibility imports
from utils.env_validation import validate_environment
from utils.env_compat import apply_env_compat  # <--- ADDED


class _RunIdLoggingFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        if getattr(record, "run_id", None) in {None, ""}:
            record.run_id = get_current_run_id() or "n/a"
        return True


_run_id_filter = _RunIdLoggingFilter()
_run_id_filter_attached = False


def _init_logging() -> None:
    global _run_id_filter_attached
    root_logger = logging.getLogger()
    if not _run_id_filter_attached:
        root_logger.addFilter(_run_id_filter)
        _run_id_filter_attached = True
    for h in root_logger.handlers:
        if _run_id_filter not in h.filters:
            h.addFilter(_run_id_filter)
    if root_logger.handlers:
        return
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s [run_id=%(run_id)s] %(message)s",
    )
    for h in logging.getLogger().handlers:
        if _run_id_filter not in h.filters:
            h.addFilter(_run_id_filter)


async def _run_once() -> None:
    from agents.workflow_orchestrator import WorkflowOrchestrator

    orchestrator = WorkflowOrchestrator()
    try:
        orchestrator.install_signal_handlers(asyncio.get_running_loop())
    except NotImplementedError:
        logging.getLogger(__name__).warning(
            "Signal handlers not supported on this platform."
        )
    try:
        await orchestrator.run()
    finally:
        await orchestrator.shutdown()


async def _daemon_loop(interval: int = 300) -> None:
    log = logging.getLogger(__name__)
    while True:
        log.info("Daemon cycle start.")
        await _run_once()
        log.info("Daemon cycle complete. Sleeping %ss.", interval)
        await asyncio.sleep(interval)


async def _async_main() -> None:
    load_dotenv()
    _init_logging()

    # COMPAT LAYER (runs BEFORE validation)
    apply_env_compat()

    if not validate_environment(strict=True):
        logging.getLogger(__name__).error("Environment validation failed; exiting.")
        return

    if setup_telemetry and os.getenv("OTEL_DISABLE_DEV", "").strip().lower() not in {
        "1",
        "true",
        "yes",
        "on",
    }:
        try:
            setup_telemetry(service_name="lead-market-insights")
        except Exception:
            logging.getLogger(__name__).warning(
                "Telemetry setup failed; continuing.", exc_info=True
            )

    run_mode = os.getenv("LEADMI_RUN_MODE", "daemon").lower()
    if run_mode == "oneshot":
        await _run_once()
    else:
        await _daemon_loop(interval=int(os.getenv("LEADMI_DAEMON_INTERVAL", "300")))


def main() -> None:
    asyncio.run(_async_main())


if __name__ == "__main__":
    main()
