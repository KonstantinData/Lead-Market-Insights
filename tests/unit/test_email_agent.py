"""Unit tests for the EmailAgent attachment and link handling."""

from __future__ import annotations

import email
from email import policy
from pathlib import Path
from typing import List

import pytest

from agents.email_agent import EmailAgent


class _DummyServer:
    def __init__(self, sent_messages: List[str]):
        self._sent_messages = sent_messages

    def __enter__(self) -> "_DummyServer":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:  # pragma: no cover - context cleanup
        return None

    def login(self, username: str, password: str) -> None:
        return None

    def sendmail(self, sender: str, recipient: str, message: str) -> None:
        self._sent_messages.append(message)


def _install_dummy_smtp(monkeypatch: pytest.MonkeyPatch, sent_messages: List[str]) -> None:
    from agents import email_agent as email_agent_module

    def _factory(*_args, **_kwargs):
        return _DummyServer(sent_messages)

    monkeypatch.setattr(email_agent_module.smtplib, "SMTP_SSL", _factory)


def test_email_agent_attaches_pdfs_and_links(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    attachment = tmp_path / "report.pdf"
    attachment.write_bytes(b"%PDF-1.4 test")

    sent_messages: List[str] = []
    _install_dummy_smtp(monkeypatch, sent_messages)

    agent = EmailAgent("smtp.example.com", 465, "user", "pass", "sender@example.com")
    portal_link = "https://crm.example.com/attachments/run-123/report"

    result = agent.send_email(
        "recipient@example.com",
        "Subject",
        "Body text",
        html_body="<p>Body</p>",
        attachments=[attachment],
        attachment_links=[portal_link],
    )

    assert result is True
    assert sent_messages, "Expected the EmailAgent to send an email"

    message = email.message_from_string(sent_messages[0], policy=policy.default)
    parts = list(message.walk())
    attachment_parts = [
        part for part in parts if part.get_content_type() == "application/pdf"
    ]
    assert attachment_parts, "Expected a PDF attachment to be included"

    text_part = next(part for part in parts if part.get_content_type() == "text/plain")
    assert "Access the dossier using the following link(s):" in text_part.get_content()
    assert portal_link in text_part.get_content()

    html_part = next(part for part in parts if part.get_content_type() == "text/html")
    assert portal_link in html_part.get_content()


def test_email_agent_handles_missing_attachments_gracefully(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    sent_messages: List[str] = []
    _install_dummy_smtp(monkeypatch, sent_messages)

    agent = EmailAgent("smtp.example.com", 465, "user", "pass", "sender@example.com")

    result = agent.send_email(
        "recipient@example.com",
        "Subject",
        "Simple body",
    )

    assert result is True
    assert sent_messages
    message = email.message_from_string(sent_messages[0], policy=policy.default)
    text_part = next(part for part in message.walk() if part.get_content_type() == "text/plain")
    assert text_part.get_content().startswith("Simple body")
