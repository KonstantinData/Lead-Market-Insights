"""Unit tests for the :mod:`agents.alert_agent` module."""

from __future__ import annotations

import asyncio
import logging
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from agents.alert_agent import AlertAgent, AlertSeverity, _maybe_sign


class DummyEmailClient:
    def __init__(self) -> None:
        self.sent = []

    async def send_email_async(self, recipient: str, subject: str, body: str) -> None:
        self.sent.append((recipient, subject, body))


@pytest.fixture
def email_channel():
    client = DummyEmailClient()
    channel = {
        "type": "email",
        "client": client,
        "recipients": ["alerts@example.com"],
        "subject_template": "[{severity}] {message}",
        "body_template": "Message: {message} (severity={severity})",
    }
    return client, channel


def test_add_channel_validates_type():
    agent = AlertAgent()

    with pytest.raises(ValueError):
        agent.add_channel({"type": "pagerduty"})


@pytest.mark.asyncio
async def test_send_alert_dispatches_to_all_channels(monkeypatch, email_channel):
    client, channel = email_channel
    slack_payloads = []
    webhook_payloads = []

    def fake_post(url, json=None, headers=None, timeout=None):
        payload = SimpleNamespace(url=url, json=json, headers=headers, timeout=timeout)
        if "slack" in url:
            slack_payloads.append(payload)
        else:
            webhook_payloads.append(payload)
        return SimpleNamespace(status_code=200)

    monkeypatch.setattr("agents.alert_agent.requests.post", fake_post)

    agent = AlertAgent(
        [
            channel,
            {"type": "slack", "webhook_url": "https://hooks.slack/test"},
            {"type": "webhook", "url": "https://example.com/alert"},
        ]
    )

    agent.send_alert("Backend down", AlertSeverity.ERROR, context={"service": "crm"})
    await asyncio.sleep(0)

    assert client.sent == [
        (
            "alerts@example.com",
            "[ERROR] Backend down",
            "Message: Backend down (severity=ERROR)",
        )
    ]
    assert slack_payloads[0].json["text"] == "[ERROR] Backend down"
    assert webhook_payloads[0].json == {
        "message": "Backend down",
        "severity": "error",
        "context": {"severity": "error", "service": "crm"},
    }


@pytest.mark.asyncio
async def test_send_alert_uses_custom_dispatcher(email_channel):
    client, channel = email_channel
    dispatched = []

    def fake_dispatcher(message, severity, context):
        dispatched.append((message, severity, context))

    channel.pop("type")
    channel["dispatcher"] = fake_dispatcher

    agent = AlertAgent([channel])
    agent.send_alert("Check systems", AlertSeverity.WARNING)
    await asyncio.sleep(0)

    assert client.sent == []
    assert dispatched == [
        ("Check systems", AlertSeverity.WARNING, {"severity": "warning"})
    ]


def test_send_via_channel_rejects_unknown_type():
    agent = AlertAgent()

    with pytest.raises(ValueError):
        agent._send_via_channel(  # type: ignore[arg-type]
            {"type": "pagerduty"},
            "Unknown",
            AlertSeverity.INFO,
            {},
        )


def test_maybe_sign_adds_hmac_header():
    payload = {"hello": "world"}

    headers = _maybe_sign(payload, "secret")

    assert "X-Signature" in headers
    assert headers["X-Signature"].startswith("sha256=")


def test_dispatch_email_requires_client_and_recipients(caplog):
    agent = AlertAgent()
    caplog.set_level(logging.WARNING)

    agent._dispatch_email(  # type: ignore[arg-type]
        {"type": "email", "recipients": []},
        "Message",
        AlertSeverity.INFO,
        {},
    )

    assert "Email channel misconfigured" in caplog.text


def test_dispatch_email_validates_async_method():
    agent = AlertAgent()
    channel = {
        "type": "email",
        "client": object(),
        "recipients": ["alerts@example.com"],
    }

    with pytest.raises(AttributeError):
        agent._dispatch_email(  # type: ignore[arg-type]
            channel,
            "Ping",
            AlertSeverity.INFO,
            {},
        )


def test_dispatch_email_logs_when_scheduler_returns_none(monkeypatch, caplog):
    agent = AlertAgent()
    caplog.set_level(logging.WARNING)

    def fake_schedule(_):
        _.close()
        return None

    monkeypatch.setattr(agent, "_schedule_coroutine", fake_schedule)

    channel = {
        "type": "email",
        "client": DummyEmailClient(),
        "recipients": ["alerts@example.com"],
    }

    agent._dispatch_email(  # type: ignore[arg-type]
        channel,
        "Ping",
        AlertSeverity.INFO,
        {},
    )

    assert "Failed to schedule email alert delivery" in caplog.text


def test_dispatch_slack_missing_webhook_logs_warning(caplog):
    agent = AlertAgent()
    caplog.set_level(logging.WARNING)

    agent._dispatch_slack(  # type: ignore[arg-type]
        {"type": "slack"},
        "Message",
        AlertSeverity.ERROR,
        {},
    )

    assert "Slack channel missing webhook URL" in caplog.text


def test_dispatch_webhook_missing_url_logs_warning(caplog):
    agent = AlertAgent()
    caplog.set_level(logging.WARNING)

    agent._dispatch_webhook(  # type: ignore[arg-type]
        {"type": "webhook"},
        "Message",
        AlertSeverity.ERROR,
        {},
    )

    assert "Webhook channel missing URL" in caplog.text


def test_dispatch_webhook_includes_signature(monkeypatch):
    captured = []

    def fake_post(url, json=None, headers=None, timeout=None):  # noqa: A002 - request api
        captured.append((url, json, headers, timeout))
        return SimpleNamespace(status_code=200)

    monkeypatch.setattr("agents.alert_agent.requests.post", fake_post)

    agent = AlertAgent()
    channel = {
        "type": "webhook",
        "url": "https://example.invalid/hook",
        "signature_key": "secret",
        "headers": {"X-Test": "1"},
    }

    agent._dispatch_webhook(  # type: ignore[arg-type]
        channel,
        "Notice",
        AlertSeverity.CRITICAL,
        {"foo": "bar"},
    )

    assert captured
    url, payload, headers, timeout = captured[0]
    assert url == "https://example.invalid/hook"
    assert payload["severity"] == "critical"
    assert headers["X-Test"] == "1"
    assert headers["X-Signature"].startswith("sha256=")
    assert timeout == 5


def test_schedule_coroutine_requires_running_loop(caplog):
    agent = AlertAgent()
    caplog.set_level(logging.ERROR)
    coro = asyncio.sleep(0)

    try:
        result = agent._schedule_coroutine(coro)
    finally:
        coro.close()

    assert result is None
    assert "Cannot dispatch email alert" in caplog.text


@pytest.mark.asyncio
async def test_schedule_coroutine_uses_task_scheduler_override():
    replacement_tasks: list[asyncio.Task[None]] = []
    original_tasks: list[asyncio.Task[None]] = []

    async def noop() -> None:
        return None

    def scheduler(original: asyncio.Task[None]) -> asyncio.Task[None]:
        original_tasks.append(original)
        replacement = asyncio.create_task(asyncio.sleep(0))
        replacement_tasks.append(replacement)
        return replacement

    agent = AlertAgent(task_scheduler=scheduler)
    task = agent._schedule_coroutine(noop())

    assert task is replacement_tasks[0]
    assert replacement_tasks[0] in agent._pending_tasks

    await original_tasks[0]
    await replacement_tasks[0]


@pytest.mark.asyncio
async def test_schedule_coroutine_retains_original_when_scheduler_returns_none():
    observed: list[asyncio.Task[None]] = []

    async def noop() -> None:
        return None

    def scheduler(task: asyncio.Task[None]) -> None:
        observed.append(task)
        return None

    agent = AlertAgent(task_scheduler=scheduler)
    task = agent._schedule_coroutine(noop())

    assert task is observed[0]
    await task


def test_send_alert_propagates_dispatcher_exceptions(caplog):
    agent = AlertAgent(
        [{"type": "slack", "dispatcher": MagicMock(side_effect=ValueError("boom"))}]
    )
    caplog.set_level(logging.ERROR)

    agent.send_alert("msg", AlertSeverity.INFO)

    assert "Failed to send alert" in caplog.text
