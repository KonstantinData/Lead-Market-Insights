import asyncio
from pathlib import Path

import pytest

import agents.workflow_orchestrator as orchestrator_module
from agents.workflow_orchestrator import WorkflowOrchestrator


try:  # pragma: no cover - optional async plugin handling
    import pytest_asyncio  # type: ignore  # noqa: F401
except ImportError:  # pragma: no cover - fallback to anyio marker
    pytestmark = pytest.mark.anyio

    @pytest.fixture
    def anyio_backend():  # pragma: no cover - ensure asyncio backend under anyio
        return "asyncio"
else:
    pytestmark = pytest.mark.asyncio


class _DummyResource:
    def __init__(self) -> None:
        self.close_calls = 0

    async def aclose(self) -> None:
        self.close_calls += 1


class _StubMasterAgent:
    def __init__(self, log_dir: Path) -> None:
        self._resource = _DummyResource()
        self.log_file_path = log_dir / "stub.log"
        self.log_file_path.write_text("", encoding="utf-8")
        self.log_filename = str(self.log_file_path)
        self.storage_agent = None
        self.closed = False

    def initialize_run(self, run_id: str) -> None:  # pragma: no cover - stub hook
        return

    async def process_all_events(self):
        return []

    def finalize_run_logs(self) -> None:  # pragma: no cover - stub hook
        return

    async def aclose(self) -> None:
        self.closed = True
        await self._resource.aclose()


async def test_shutdown_cancels_tasks_and_flushes(monkeypatch, tmp_path: Path) -> None:
    master_agent = _StubMasterAgent(tmp_path)
    orchestrator = WorkflowOrchestrator(master_agent=master_agent)

    flush_calls: list[float] = []

    async def fake_flush(timeout: float = 0.0) -> None:
        flush_calls.append(timeout)

    monkeypatch.setattr(orchestrator_module, "flush_telemetry", fake_flush)

    await orchestrator.run()

    blocker = asyncio.Event()
    task = orchestrator.track_background_task(asyncio.create_task(blocker.wait()))

    await orchestrator.shutdown(reason="test", timeout=0.1)

    assert task.cancelled()
    assert master_agent.closed is True
    assert master_agent._resource.close_calls == 1  # type: ignore[attr-defined]
    assert flush_calls, "flush_telemetry should have been invoked"


async def test_shutdown_is_idempotent(monkeypatch, tmp_path: Path) -> None:
    master_agent = _StubMasterAgent(tmp_path)
    orchestrator = WorkflowOrchestrator(master_agent=master_agent)

    flush_calls = 0

    async def fake_flush(timeout: float = 0.0) -> None:
        nonlocal flush_calls
        flush_calls += 1

    monkeypatch.setattr(orchestrator_module, "flush_telemetry", fake_flush)

    await orchestrator.shutdown()
    await orchestrator.shutdown()

    assert master_agent.closed is True
    assert master_agent._resource.close_calls == 1  # type: ignore[attr-defined]
    assert flush_calls == 1
