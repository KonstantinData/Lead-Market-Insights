"""Unit tests for the :mod:`agents.alert_agent` module."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from agents.alert_agent import AlertAgent, AlertSeverity


class DummyEmailClient:
    def __init__(self) -> None:
        self.sent = []

    def send_email(self, recipient: str, subject: str, body: str) -> None:
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


def test_send_alert_dispatches_to_all_channels(monkeypatch, email_channel):
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


def test_send_alert_uses_custom_dispatcher(email_channel):
    client, channel = email_channel
    dispatched = []

    def fake_dispatcher(message, severity, context):
        dispatched.append((message, severity, context))

    channel.pop("type")
    channel["dispatcher"] = fake_dispatcher

    agent = AlertAgent([channel])
    agent.send_alert("Check systems", AlertSeverity.WARNING)

    assert client.sent == []
    assert dispatched == [("Check systems", AlertSeverity.WARNING, {"severity": "warning"})]
