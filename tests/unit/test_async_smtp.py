from unittest.mock import AsyncMock, MagicMock

import aiosmtplib
import pytest

from utils import async_smtp


@pytest.mark.asyncio
async def test_send_email_ssl_requires_recipient():
    with pytest.raises(ValueError):
        await async_smtp.send_email_ssl(
            host="smtp.example.com",
            username="user",
            password="secret",
            message="msg",
            to_addrs=[],
        )


@pytest.mark.asyncio
async def test_send_email_ssl_happy_path(monkeypatch):
    client = MagicMock()
    client.connect = AsyncMock()
    client.login = AsyncMock()
    client.sendmail = AsyncMock()
    client.quit = AsyncMock()

    monkeypatch.setattr("aiosmtplib.SMTP", MagicMock(return_value=client))

    await async_smtp.send_email_ssl(
        host="smtp.example.com",
        username="user",
        password="secret",
        message="msg",
        to_addrs=["to@example.com"],
        port=465,
        timeout=5.0,
    )

    client.connect.assert_awaited_once()
    client.login.assert_awaited_once_with("user", "secret")
    client.sendmail.assert_awaited_once_with(
        from_addr="user", to_addrs=["to@example.com"], message="msg"
    )
    client.quit.assert_awaited_once()


@pytest.mark.asyncio
async def test_send_email_ssl_quit_failure_falls_back_to_close(monkeypatch):
    client = MagicMock()
    client.connect = AsyncMock()
    client.login = AsyncMock()
    client.sendmail = AsyncMock()
    client.quit = AsyncMock(side_effect=aiosmtplib.errors.SMTPException("fail"))
    client.close = AsyncMock()

    monkeypatch.setattr("aiosmtplib.SMTP", MagicMock(return_value=client))

    await async_smtp.send_email_ssl(
        host="smtp.example.com",
        username="user",
        password="secret",
        message="msg",
        to_addrs=["to@example.com"],
    )

    client.close.assert_awaited_once()
