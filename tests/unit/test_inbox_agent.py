from __future__ import annotations

import asyncio
from email.message import EmailMessage
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


@pytest.mark.asyncio
async def test_poll_once_fetches_from_imap(monkeypatch: pytest.MonkeyPatch) -> None:
    email_message = EmailMessage()
    email_message["Subject"] = "Audit ID: fetch-123"
    email_message["From"] = "Lead Bot <bot@example.com>"
    email_message["To"] = "ops@example.com"
    email_message["Date"] = "Mon, 01 Jan 2024 10:00:00 +0000"
    email_message["X-Leadmi-Audit-Id"] = "fetch-123"
    email_message.set_content("Please review dossier.")
    raw_message = email_message.as_bytes()

    class FakeIMAP:
        instances: list["FakeIMAP"] = []

        def __init__(self, host: str, port: int) -> None:
            self.host = host
            self.port = port
            self.login_args: Optional[tuple[str, str]] = None
            self.selected: Optional[str] = None
            self.fetch_calls: list[tuple[bytes, str]] = []
            self.store_calls: list[tuple[bytes, str, str]] = []
            self.logged_out = False
            FakeIMAP.instances.append(self)

        def login(self, username: str, password: str):  # type: ignore[override]
            self.login_args = (username, password)
            return "OK", []

        def select(self, mailbox: str):  # type: ignore[override]
            self.selected = mailbox
            return "OK", [b"1"]

        def search(self, charset: Optional[str], *criteria: str):  # type: ignore[override]
            return "OK", [b"1"]

        def fetch(self, message_id: bytes, query: str):  # type: ignore[override]
            self.fetch_calls.append((message_id, query))
            header = b'1 (UID 555 RFC822 {123})'
            return "OK", [(header, raw_message)]

        def store(self, message_id: bytes, command: str, flags: str):  # type: ignore[override]
            self.store_calls.append((message_id, command, flags))
            return "OK", []

        def logout(self):  # type: ignore[override]
            self.logged_out = True
            return "BYE", []

    monkeypatch.setattr("polling.inbox_agent.imaplib.IMAP4_SSL", FakeIMAP)
    monkeypatch.setattr("polling.inbox_agent.imaplib.IMAP4", FakeIMAP)

    config = {
        "imap_host": "imap.example.com",
        "imap_username": "user",
        "imap_password": "pass",
        "imap_mailbox": "INBOX",
        "imap_use_ssl": True,
    }

    agent = InboxAgent(config=config, poll_interval=0)
    handler = AsyncMock()
    agent.register_handler(handler)

    processed = await agent.poll_once()

    assert processed == 1
    assert FakeIMAP.instances, "Fake IMAP server not instantiated"
    fake_server = FakeIMAP.instances[0]
    assert fake_server.login_args == ("user", "pass")
    assert fake_server.selected == "INBOX"
    assert fake_server.store_calls == [(b"1", "+FLAGS", "(\\Seen)")]
    assert fake_server.logged_out is True

    call = handler.await_args
    message_arg, audit_id = call.args
    assert audit_id == "fetch-123"
    assert message_arg.id == "555"
    assert message_arg.subject == "Audit ID: fetch-123"
    assert message_arg.sender == "bot@example.com"
    assert "Please review dossier" in message_arg.body
    assert message_arg.headers["X-Leadmi-Audit-Id"] == "fetch-123"
    assert message_arg.received_at is not None
