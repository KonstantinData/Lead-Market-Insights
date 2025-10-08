"""SMTP email helper for HITL notifications."""

from __future__ import annotations

import os
import smtplib
import ssl
from email.message import EmailMessage
from email.utils import make_msgid
from typing import Dict, Optional

DEFAULT_TIMEOUT = 30


def _normalize_bool(value: Optional[str], *, default: bool) -> bool:
    if value is None:
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _validate_mode(port: int, use_ssl: bool, use_starttls: bool) -> None:
    if use_ssl and use_starttls:
        raise RuntimeError("Invalid config: USE_SSL and STARTTLS cannot both be true.")
    if port == 465 and use_starttls:
        raise RuntimeError("Port 465 must not use STARTTLS.")
    if port == 587 and not use_starttls:
        raise RuntimeError("Port 587 requires STARTTLS.")


def _build_message(
    sender: str,
    recipient: str,
    subject: str,
    body: str,
    headers: Optional[Dict[str, str]] = None,
) -> EmailMessage:
    message = EmailMessage()
    message["From"] = sender
    message["To"] = recipient
    message["Subject"] = subject
    if headers:
        for key, value in headers.items():
            message[key] = value
    message.set_content(body)
    if "Message-ID" not in message:
        message["Message-ID"] = make_msgid()
    return message


def send_mail(to: str, subject: str, body: str, *, timeout: int = DEFAULT_TIMEOUT) -> None:
    """Send a simple email using SMTP settings sourced from the environment."""

    host = os.environ["SMTP_HOST"]
    port = int(os.environ.get("SMTP_PORT", "465"))
    use_ssl = _normalize_bool(os.environ.get("SMTP_USE_SSL"), default=(port == 465))
    use_starttls = _normalize_bool(
        os.environ.get("SMTP_STARTTLS"), default=(port == 587)
    )
    _validate_mode(port, use_ssl, use_starttls)

    username = os.environ.get("SMTP_USERNAME")
    password = os.environ.get("SMTP_PASSWORD")
    sender = os.environ.get("SMTP_FROM") or username or "noreply@example.com"

    message = _build_message(sender, to, subject, body)

    if use_ssl or port == 465:
        context = ssl.create_default_context()
        with smtplib.SMTP_SSL(host, port, context=context, timeout=timeout) as smtp:
            if username and password:
                smtp.login(username, password)
            smtp.send_message(message)
    else:
        with smtplib.SMTP(host, port, timeout=timeout) as smtp:
            smtp.ehlo()
            if use_starttls:
                context = ssl.create_default_context()
                smtp.starttls(context=context)
                smtp.ehlo()
            if username and password:
                smtp.login(username, password)
            smtp.send_message(message)


class EmailAgent:
    """Lightweight SMTP client with configurable TLS/SSL handling."""

    def __init__(
        self,
        host: str,
        port: int,
        username: str,
        password: str,
        sender: Optional[str] = None,
        *,
        use_ssl: Optional[bool] = None,
        use_starttls: Optional[bool] = None,
        timeout: int = DEFAULT_TIMEOUT,
    ) -> None:
        if not host:
            raise ValueError("SMTP host must be provided")
        if not port:
            raise ValueError("SMTP port must be provided")
        self.host = host
        self.port = int(port)
        self.username = username
        self.password = password
        self.sender = sender or username or "noreply@example.com"
        self.timeout = timeout

        if use_ssl is None and use_starttls is None:
            inferred_ssl = self.port == 465
            inferred_starttls = self.port == 587
        else:
            inferred_ssl = bool(use_ssl)
            inferred_starttls = bool(use_starttls)
        _validate_mode(self.port, inferred_ssl, inferred_starttls)
        self._use_ssl = inferred_ssl
        self._use_starttls = inferred_starttls

    def _ensure_credentials(self) -> None:
        if not self.username or not self.password:
            raise RuntimeError(
                "SMTP credentials are required to send HITL emails; username/password missing"
            )

    def send_email(
        self,
        recipient: str,
        subject: str,
        body: str,
        headers: Optional[Dict[str, str]] = None,
    ) -> str:
        """Send a plain-text email and return the message identifier."""

        self._ensure_credentials()
        message = _build_message(self.sender, recipient, subject, body, headers=headers)

        if self._use_ssl or self.port == 465:
            context = ssl.create_default_context()
            with smtplib.SMTP_SSL(
                self.host, self.port, context=context, timeout=self.timeout
            ) as smtp:
                smtp.login(self.username, self.password)
                smtp.send_message(message)
        else:
            with smtplib.SMTP(self.host, self.port, timeout=self.timeout) as smtp:
                smtp.ehlo()
                if self._use_starttls:
                    context = ssl.create_default_context()
                    smtp.starttls(context=context)
                    smtp.ehlo()
                smtp.login(self.username, self.password)
                smtp.send_message(message)

        return str(message["Message-ID"]) or ""


__all__ = ["EmailAgent", "send_mail"]
