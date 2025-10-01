"""Regression tests for the main module logging bootstrap."""

from __future__ import annotations

import logging

import main
from utils import observability


def _reset_logging_state() -> None:
    """Return the logging module to a clean slate for deterministic tests."""

    root_logger = logging.getLogger()
    for handler in list(root_logger.handlers):
        root_logger.removeHandler(handler)
        try:
            handler.close()
        except Exception:  # pragma: no cover - defensive cleanup
            pass
    for existing_filter in list(root_logger.filters):
        root_logger.removeFilter(existing_filter)
    logging.setLogRecordFactory(logging.LogRecord)
    if hasattr(main, "_run_id_filter_attached"):
        main._run_id_filter_attached = False


def test_init_logging_injects_default_run_id(capsys):
    _reset_logging_state()

    main._init_logging()

    logging.getLogger(__name__).info(
        "log message emitted before orchestrator instantiation"
    )
    captured = capsys.readouterr()
    assert "run_id=n/a" in captured.err


def test_logging_filter_respects_existing_run_id(capsys):
    _reset_logging_state()

    main._init_logging()
    observability.configure_observability(force=True)

    with observability.workflow_run(run_id="run-from-test"):
        logging.getLogger(__name__).info("log message with run context")
    captured = capsys.readouterr()
    assert "run_id=run-from-test" in captured.err
