# Explanation:
# Wire the nested SMTP config (settings.smtp.*) into the orchestrator as `.email`
# so HITL mails to the event organizer can be sent from within the agent flow.

import asyncio
import logging
from contextvars import ContextVar
from datetime import datetime, timezone
from types import SimpleNamespace

from config.config import settings
from agents.workflow_orchestrator import WorkflowOrchestrator
from utils import observability
from utils.email_agent import EmailAgent

current_run_id_var: ContextVar[str] = ContextVar("current_run_id", default="unassigned")

_run_id_filter_attached = False


class _RunIdFilter(logging.Filter):
    """Ensure every log record carries the current workflow run identifier."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.run_id = observability.get_current_run_id()
        return True


_run_id_filter = _RunIdFilter()


def _init_logging() -> None:
    """Configure structured logging once per process."""

    global _run_id_filter_attached

    root_logger = logging.getLogger()
    if not root_logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(
            logging.Formatter(
                "%(asctime)s %(levelname)s [run_id=%(run_id)s] %(name)s %(message)s"
            )
        )
        root_logger.addHandler(handler)
    else:
        for handler in root_logger.handlers:
            formatter = handler.formatter
            if formatter is None or "%(run_id)" not in getattr(formatter, "_fmt", ""):
                handler.setFormatter(
                    logging.Formatter(
                        "%(asctime)s %(levelname)s [run_id=%(run_id)s] %(name)s %(message)s"
                    )
                )

    if not _run_id_filter_attached:
        root_logger.addFilter(_run_id_filter)
        for handler in root_logger.handlers:
            handler.addFilter(_run_id_filter)
        _run_id_filter_attached = True

    root_logger.setLevel(logging.INFO)


def _assign_new_run_id() -> str:
    """Generate unique run_id with timestamp (UTC) for traceability."""
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"run-{ts}"


def _build_comm_backend_from_settings() -> SimpleNamespace:
    """
    Build a tiny communication backend exposing `.email` for agents.
    Uses nested settings.smtp.{host,port,username,password,sender,secure}.
    """
    smtp = settings.smtp  # dataclass SmtpSettings

    required = ("host", "port", "username", "password", "sender")
    missing = [k for k in required if not getattr(smtp, k, None)]
    if missing:
        raise RuntimeError(f"Incomplete SMTP config: missing {', '.join(missing)}")

    email = EmailAgent(
        host=smtp.host,
        port=int(smtp.port),
        username=smtp.username,
        password=smtp.password,
        sender=smtp.sender,
        use_tls=bool(getattr(smtp, "secure", True)),
    )
    return SimpleNamespace(email=email)


async def _run_once(run_id: str) -> None:
    """Single daemon cycle — provide comm backend, then run orchestrator."""
    current_run_id_var.set(run_id)
    comm_backend = _build_comm_backend_from_settings()

    orch = WorkflowOrchestrator(
        run_id=run_id,
        communication_backend=comm_backend,  # <- enables HITL emails
    )
    logging.getLogger(__name__).info(
        "Orchestrator ready (run_id=%s, email wired)", run_id
    )
    await orch.run()


def main() -> None:
    _init_logging()
    logging.info("Environment validation passed.")
    run_id = _assign_new_run_id()
    logging.info("Daemon cycle start for run.id=%s", run_id)
    asyncio.run(_run_once(run_id))


if __name__ == "__main__":
    main()
