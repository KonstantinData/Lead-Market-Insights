import logging
from typing import List

import pytest

import agents.workflow_orchestrator as workflow_module
import main
from agents.workflow_orchestrator import WorkflowOrchestrator
from utils.observability import (
    current_run_id_var,
    generate_run_id,
    observe_operation,
    workflow_run,
)


@pytest.mark.asyncio
async def test_daemon_loop_generates_unique_run_ids(monkeypatch, caplog):
    caplog.set_level(logging.INFO)
    main._init_logging()

    generated_run_ids: List[str] = ["run-test-1", "run-test-2", "run-test-3"]

    async def fake_run_once(run_id: str) -> None:
        logging.getLogger("test.daemon").info("fake run executed")
        if len(generated_run_ids) <= 1:
            raise StopAsyncIteration
        generated_run_ids.pop(0)

    def prepare_run() -> str:
        next_id = generated_run_ids[0]
        current_run_id_var.set(next_id)
        return next_id

    initial_id = prepare_run()

    monkeypatch.setattr(main, "_run_once", fake_run_once)

    with pytest.raises(StopAsyncIteration):
        await main._daemon_loop(
            interval=0, prepare_run=prepare_run, initial_run_id=initial_id
        )

    cycle_records = [
        record
        for record in caplog.records
        if "Daemon cycle start" in record.message or record.name == "test.daemon"
    ]
    run_ids = [getattr(record, "run_id", "") for record in cycle_records]
    assert len(run_ids) >= 3
    unique_ids = {rid for rid in run_ids if rid}
    assert len(unique_ids) >= 2

    current_run_id_var.set("")


@pytest.mark.asyncio
async def test_run_once_never_logs_placeholder_run_id(monkeypatch, caplog):
    caplog.set_level(logging.INFO)
    main._init_logging()

    class FakeOrchestrator:
        def __init__(self, run_id: str, *_, **__):
            self.run_id = run_id
            logging.getLogger("test.run").info("fake orchestrator created")

        def install_signal_handlers(self, *_args, **_kwargs):
            return None

        async def run(self) -> None:
            logging.getLogger("test.run").info("fake orchestrator run")

        async def shutdown(self) -> None:
            logging.getLogger("test.run").info("fake orchestrator shutdown")

    monkeypatch.setattr(workflow_module, "WorkflowOrchestrator", FakeOrchestrator)

    run_id = "run-placeholder-check"
    await main._run_once(run_id)

    for record in caplog.records:
        if record.name.startswith("test.run") or record.name == "main":
            assert getattr(record, "run_id", "") not in {"unassigned", "n/a"}

    current_run_id_var.set("")


def test_observe_operation_attaches_run_id_to_spans():
    run_id = generate_run_id()
    current_run_id_var.set(run_id)

    with observe_operation("trigger_detection") as span:
        assert span.attributes["workflow.run_id"] == run_id
        assert span.attributes["run.id"] == run_id

    current_run_id_var.set("")


def test_workflow_orchestrator_requires_run_id():
    with pytest.raises(ValueError):
        WorkflowOrchestrator(run_id="")


def test_workflow_run_context_requires_run_id():
    current_run_id_var.set("")
    with pytest.raises(RuntimeError):
        with workflow_run():
            pass
