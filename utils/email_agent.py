"""SMTP email helper for HITL notifications."""

from __future__ import annotations

import smtplib
import ssl
from email.message import EmailMessage
from email.utils import make_msgid
from typing import Dict, Optional


class EmailAgent:
    """Lightweight SMTP client with optional STARTTLS support."""

    def __init__(
        self,
        host: str,
        port: int,
        username: str,
        password: str,
        use_tls: bool = True,
        *,
        timeout: int = 30,
    ) -> None:
        if not host:
            raise ValueError("SMTP host must be provided")
        if not port:
            raise ValueError("SMTP port must be provided")
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.use_tls = use_tls
        self.timeout = timeout

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

        message = EmailMessage()
        message["From"] = self.username
        message["To"] = recipient
        message["Subject"] = subject
        if headers:
            for key, value in headers.items():
                message[key] = value
        message.set_content(body)
        if "Message-ID" not in message:
            message["Message-ID"] = make_msgid()

        context = ssl.create_default_context()
        with smtplib.SMTP(self.host, self.port, timeout=self.timeout) as server:
            if self.use_tls:
                server.starttls(context=context)
            server.login(self.username, self.password)
            server.send_message(message)

        return str(message["Message-ID"]) or ""


__all__ = ["EmailAgent"]
