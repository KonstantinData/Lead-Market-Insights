"""Shared asynchronous SMTP helpers."""

from __future__ import annotations

from typing import Sequence

import aiosmtplib
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_random_exponential,
)

from .retry import DEFAULT_MAX_ATTEMPTS, INITIAL_BACKOFF_SECONDS, MAX_BACKOFF_SECONDS

DEFAULT_SMTP_PORT = 465
DEFAULT_TIMEOUT = 20.0


@retry(
    reraise=True,
    stop=stop_after_attempt(DEFAULT_MAX_ATTEMPTS),
    wait=wait_random_exponential(
        multiplier=INITIAL_BACKOFF_SECONDS, max=MAX_BACKOFF_SECONDS
    ),
    retry=retry_if_exception_type((aiosmtplib.errors.SMTPException, TimeoutError)),
)
async def send_email_ssl(
    *,
    host: str,
    username: str,
    password: str,
    message: str,
    to_addrs: Sequence[str],
    port: int = DEFAULT_SMTP_PORT,
    timeout: float = DEFAULT_TIMEOUT,
) -> None:
    if not to_addrs:
        raise ValueError("to_addrs must include at least one recipient")

    client = aiosmtplib.SMTP(hostname=host, port=port, use_tls=True, timeout=timeout)
    await client.connect()
    try:
        await client.login(username, password)
        await client.sendmail(
            from_addr=username, to_addrs=list(to_addrs), message=message
        )
    finally:
        try:
            await client.quit()
        except aiosmtplib.errors.SMTPException:
            await client.close()
