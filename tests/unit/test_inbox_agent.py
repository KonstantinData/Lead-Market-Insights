from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import Optional
from unittest.mock import AsyncMock

import pytest

from polling.inbox_agent import InboxAgent, InboxMessage


def _configured_settings() -> SimpleNamespace:
    return SimpleNamespace(
        imap_host="imap.example.com",
        imap_user="user",
        imap_password="pass",
    )


@pytest.mark.asyncio
async def test_dispatch_invokes_handlers_and_detects_header_audit_id() -> None:
    agent = InboxAgent(config=_configured_settings().__dict__, poll_interval=0)
    handler_one = AsyncMock()
    handler_two = AsyncMock()
    agent.register_handler(handler_one)
    agent.register_handler(handler_two)

    message = InboxMessage(
        id="msg-1",
        subject="Manual review required",
        sender="operator@example.com",
        headers={"X-Leadmi-Audit-Id": "audit-123"},
    )

    handled = await agent._dispatch_message(message)

    assert handled is True
    handler_one.assert_awaited_once_with(message, "audit-123")
    handler_two.assert_awaited_once_with(message, "audit-123")


@pytest.mark.asyncio
async def test_dispatch_detects_audit_id_from_subject() -> None:
    agent = InboxAgent(config=_configured_settings().__dict__, poll_interval=0)
    handler = AsyncMock()
    agent.register_handler(handler)

    message = InboxMessage(
        id="msg-2",
        subject="Re: Workflow update (Audit ID: subj-456)",
        sender="operator@example.com",
        headers={},
    )

    await agent._dispatch_message(message)

    handler.assert_awaited_once_with(message, "subj-456")


@pytest.mark.asyncio
async def test_dispatch_without_handlers_is_ignored() -> None:
    agent = InboxAgent(config=_configured_settings().__dict__, poll_interval=0)
    message = InboxMessage(
        id="msg-3",
        subject="No handler",
        sender="operator@example.com",
    )

    handled = await agent._dispatch_message(message)

    assert handled is False


@pytest.mark.asyncio
async def test_dispatch_skips_duplicate_audit_ids() -> None:
    agent = InboxAgent(config=_configured_settings().__dict__, poll_interval=0)
    handler = AsyncMock()
    agent.register_handler(handler)

    message = InboxMessage(
        id="msg-4",
        subject="Audit update",
        sender="operator@example.com",
        headers={"X-Leadmi-Audit-Id": "dup-789"},
    )

    first = await agent._dispatch_message(message)
    second = await agent._dispatch_message(message)

    assert first is True
    assert second is False
    handler.assert_awaited_once()


@pytest.mark.asyncio
async def test_dispatch_concurrent_duplicates_respect_lock() -> None:
    agent = InboxAgent(config=_configured_settings().__dict__, poll_interval=0)
    calls: list[tuple[str, Optional[str]]] = []

    async def handler(msg: InboxMessage, audit_id: Optional[str]) -> None:
        calls.append((msg.id, audit_id))
        await asyncio.sleep(0.01)

    agent.register_handler(handler)

    first = InboxMessage(
        id="msg-5a",
        subject="Audit check",
        sender="operator@example.com",
        headers={"X-Leadmi-Audit-Id": "lock-123"},
    )
    second = InboxMessage(
        id="msg-5b",
        subject="Audit check",
        sender="operator@example.com",
        headers={"X-Leadmi-Audit-Id": "lock-123"},
    )

    results = await asyncio.gather(
        agent._dispatch_message(first), agent._dispatch_message(second)
    )

    assert results.count(True) == 1
    assert len(calls) == 1
    assert calls[0] == ("msg-5a", "lock-123") or calls[0] == ("msg-5b", "lock-123")


@pytest.mark.asyncio
async def test_poll_once_processes_messages_and_counts() -> None:
    agent = InboxAgent(config=_configured_settings().__dict__, poll_interval=0)
    handler = AsyncMock()
    agent.register_handler(handler)

    first = InboxMessage(
        id="poll-1",
        subject="Audit ID: poll-1",
        sender="operator@example.com",
        headers={},
    )
    second = InboxMessage(
        id="poll-2",
        subject="Audit update",
        sender="operator@example.com",
        headers={"X-Leadmi-Audit-Id": "poll-2"},
    )

    agent.fetch_new_messages = AsyncMock(return_value=[first, second])  # type: ignore[attr-defined]

    processed = await agent.poll_once()

    assert processed == 2
    awaited = [entry.args for entry in handler.await_args_list]
    assert (first, "poll-1") in awaited
    assert (second, "poll-2") in awaited


@pytest.mark.asyncio
async def test_poll_once_respects_configuration_guard() -> None:
    agent = InboxAgent(config={}, poll_interval=0)
    agent.fetch_new_messages = AsyncMock(return_value=[])  # type: ignore[attr-defined]

    processed = await agent.poll_once()

    assert processed == 0
    agent.fetch_new_messages.assert_not_awaited()


@pytest.mark.asyncio
async def test_start_polling_loop_handles_cancellation() -> None:
    agent = InboxAgent(config=_configured_settings().__dict__, poll_interval=0.01)
    handler = AsyncMock()
    agent.register_handler(handler)

    message = InboxMessage(
        id="loop-1",
        subject="Audit update",
        sender="operator@example.com",
        headers={"X-Leadmi-Audit-Id": "loop-1"},
    )

    agent.fetch_new_messages = AsyncMock(return_value=[message])  # type: ignore[attr-defined]

    task = asyncio.create_task(agent.start_polling_loop())
    await asyncio.sleep(0.05)
    task.cancel()

    with pytest.raises(asyncio.CancelledError):
        await task

    handler.assert_awaited_once_with(message, "loop-1")


@pytest.mark.asyncio
async def test_start_polling_loop_skips_when_disabled() -> None:
    agent = InboxAgent(config={}, poll_interval=0.01)
    agent.fetch_new_messages = AsyncMock(
        return_value=[InboxMessage(id="skip", subject="", sender="", headers={})]
    )  # type: ignore[attr-defined]

    task = asyncio.create_task(agent.start_polling_loop())
    await asyncio.sleep(0.05)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    agent.fetch_new_messages.assert_not_awaited()
