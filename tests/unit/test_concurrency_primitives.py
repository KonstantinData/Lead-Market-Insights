"""Tests for concurrency primitives such as the logging semaphore."""

from __future__ import annotations

import asyncio
from typing import List

import pytest

from utils import concurrency as concurrency_module
from utils.concurrency import LoggingSemaphore


@pytest.mark.asyncio
async def test_logging_semaphore_limits_concurrent_access() -> None:
    semaphore = LoggingSemaphore("test", 2)
    release_event = asyncio.Event()
    active_counts: List[int] = []

    async def worker() -> None:
        async with semaphore:
            active_counts.append(semaphore.active)
            await release_event.wait()

    tasks = [asyncio.create_task(worker()) for _ in range(3)]

    # Allow two tasks to acquire the semaphore before releasing them.
    while len(active_counts) < semaphore.limit:
        await asyncio.sleep(0)
    assert max(active_counts) <= semaphore.limit

    release_event.set()
    await asyncio.gather(*tasks)

    # Once released the active counter should drop back to zero.
    assert semaphore.active == 0


@pytest.mark.asyncio
async def test_logging_semaphore_releases_on_cancellation() -> None:
    semaphore = LoggingSemaphore("test", 1)
    entered = asyncio.Event()
    second_started = asyncio.Event()

    async def holder() -> None:
        async with semaphore:
            entered.set()
            await asyncio.sleep(1)

    async def waiter() -> None:
        async with semaphore:
            second_started.set()

    task1 = asyncio.create_task(holder())
    await entered.wait()

    waiter_task = asyncio.create_task(waiter())
    await asyncio.sleep(0)
    task1.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task1

    await asyncio.wait_for(second_started.wait(), timeout=0.2)
    await waiter_task
    assert semaphore.active == 0


def test_resolve_limit_with_invalid_values(monkeypatch, caplog):
    caplog.set_level("WARNING")
    monkeypatch.delenv("MAX_CONCURRENT_TEST", raising=False)
    assert concurrency_module._resolve_limit("MAX_CONCURRENT_TEST", 3) == 3

    monkeypatch.setenv("MAX_CONCURRENT_TEST", "not-an-int")
    assert concurrency_module._resolve_limit("MAX_CONCURRENT_TEST", 4) == 4
    assert "Invalid value" in caplog.text

    caplog.clear()
    monkeypatch.setenv("MAX_CONCURRENT_TEST", "0")
    assert concurrency_module._resolve_limit("MAX_CONCURRENT_TEST", 5) == 5
    assert "must be greater than zero" in caplog.text


def test_normalise_limit_handles_bad_overrides(caplog):
    caplog.set_level("WARNING")
    assert concurrency_module._normalise_limit(None, fallback=2, name="TEST_LIMIT") == 2
    assert (
        concurrency_module._normalise_limit("bad", fallback=3, name="TEST_LIMIT") == 3
    )
    assert "Invalid override" in caplog.text

    caplog.clear()
    assert concurrency_module._normalise_limit(0, fallback=3, name="TEST_LIMIT") == 3
    assert "override must be positive" in caplog.text


@pytest.mark.asyncio
async def test_run_in_task_group_executes_all():
    executed: List[str] = []

    async def worker(name: str) -> None:
        executed.append(name)

    await concurrency_module.run_in_task_group(
        [lambda n=name: worker(n) for name in ("a", "b", "c")]
    )

    assert executed == ["a", "b", "c"]


@pytest.mark.asyncio
async def test_run_in_task_group_raises_exception_group(monkeypatch):
    monkeypatch.delattr(asyncio, "TaskGroup", raising=False)

    async def ok() -> None:
        return None

    async def boom() -> None:
        raise RuntimeError("boom")

    with pytest.raises(concurrency_module.ExceptionGroup) as excinfo:
        await concurrency_module.run_in_task_group([lambda: ok(), lambda: boom()])

    assert any(isinstance(err, RuntimeError) for err in excinfo.value.exceptions)


def test_reload_limits_updates_semaphores():
    original_hubspot = concurrency_module._HUBSPOT_LIMIT
    original_research = concurrency_module._RESEARCH_LIMIT

    try:
        concurrency_module.reload_limits(hubspot=2, research=4)
        assert concurrency_module.HUBSPOT_SEMAPHORE.limit == 2
        assert concurrency_module.RESEARCH_TASK_SEMAPHORE.limit == 4
    finally:
        concurrency_module.reload_limits(
            hubspot=original_hubspot, research=original_research
        )
