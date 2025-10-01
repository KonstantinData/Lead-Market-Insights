"""Tests for concurrency primitives such as the logging semaphore."""

from __future__ import annotations

import asyncio
from typing import List

import pytest

from utils.concurrency import LoggingSemaphore


pytestmark = pytest.mark.asyncio


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
