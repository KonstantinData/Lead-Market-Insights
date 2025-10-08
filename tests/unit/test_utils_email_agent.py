from __future__ import annotations

from email.message import EmailMessage

import pytest


class DummySMTP:
    def __init__(self):
        self.started_tls = False
        self.logged_in = None
        self.sent_message: EmailMessage | None = None

    def __call__(self, host, port, timeout):
        self.host = host
        self.port = port
        self.timeout = timeout
        return self

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def ehlo(self):
        return ("dummy", "ok")

    def starttls(self, *, context):
        self.started_tls = True

    def login(self, username, password):
        self.logged_in = (username, password)

    def send_message(self, message):
        self.sent_message = message


def test_email_agent_sends_message_with_headers(monkeypatch):
    from utils.email_agent import EmailAgent

    dummy = DummySMTP()
    monkeypatch.setattr("utils.email_agent.smtplib.SMTP", dummy)

    agent = EmailAgent("smtp.example.com", 587, "mailer@example.com", "secret")
    message_id = agent.send_email(
        "ops@example.com",
        "HITL request",
        "body text",
        headers={"X-Test": "1"},
    )

    assert message_id
    assert dummy.started_tls is True
    assert dummy.logged_in == ("mailer@example.com", "secret")
    assert dummy.sent_message is not None
    assert dummy.sent_message["To"] == "ops@example.com"
    assert dummy.sent_message["X-Test"] == "1"


def test_email_agent_requires_credentials():
    from utils.email_agent import EmailAgent

    agent = EmailAgent("smtp.example.com", 587, "", "")

    with pytest.raises(RuntimeError) as exc:
        agent.send_email("ops@example.com", "Subject", "Body")

    assert "SMTP credentials" in str(exc.value)
