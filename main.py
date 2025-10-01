import asyncio
import logging
import os
from dotenv import load_dotenv

from utils.observability import get_current_run_id

try:
    from utils.telemetry import setup_telemetry
except ImportError:
    setup_telemetry = None  # type: ignore

from utils.env_validation import validate_environment
from utils.env_compat import apply_env_compat


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
    # Lädt lokal .env (im Container durch SETTINGS_SKIP_DOTENV=1 irrelevant)
    load_dotenv()

    # Legacy-Kompatibilität (OPEN_AI_KEY -> OPENAI_API_KEY)
    apply_env_compat()

    _init_logging()

    if not validate_environment(strict=True):
        logging.getLogger(__name__).error("Environment validation failed; exiting.")
        return

    # Telemetrie (Traces)
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
                "Telemetry setup failed; continuing without instrumentation.",
                exc_info=True,
            )

    run_mode = os.getenv("LEADMI_RUN_MODE", "daemon").lower()
    if run_mode == "oneshot":
        await _run_once()
    else:
        interval = int(os.getenv("LEADMI_DAEMON_INTERVAL", "300"))
        await _daemon_loop(interval=interval)


def main() -> None:
    asyncio.run(_async_main())


if __name__ == "__main__":
    main()
