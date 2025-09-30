"""Lightweight stub of aiosmtplib for testing without external dependency."""

from __future__ import annotations

class errors:
    class SMTPException(Exception):
        """Base SMTP exception used by the stub."""


class SMTP:
    def __init__(self, *, hostname: str, port: int, use_tls: bool, timeout: float):
        self.hostname = hostname
        self.port = port
        self.use_tls = use_tls
        self.timeout = timeout
        self._closed = False
        self.sent_messages = []

    async def connect(self) -> None:
        return None

    async def login(self, username: str, password: str) -> None:
        return None

    async def sendmail(self, from_addr: str, to_addrs, message: str) -> None:
        self.sent_messages.append((from_addr, list(to_addrs), message))

    async def quit(self) -> None:
        self._closed = True

    async def close(self) -> None:
        self._closed = True
