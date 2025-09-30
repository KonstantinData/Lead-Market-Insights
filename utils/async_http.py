"""Shared asynchronous HTTP client utilities."""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Mapping, Optional

import httpx

# Replaced wait_exponential_jitter with wait_random_exponential (actual Tenacity API)
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_random_exponential,
)

from .retry import DEFAULT_MAX_ATTEMPTS, INITIAL_BACKOFF_SECONDS, MAX_BACKOFF_SECONDS

logger = logging.getLogger(__name__)

DEFAULT_CONNECT_TIMEOUT = 5.0
DEFAULT_READ_TIMEOUT = 20.0
DEFAULT_TOTAL_TIMEOUT = 30.0


def _log_retry(retry_state) -> None:
    if retry_state.attempt_number > 1:
        logger.warning(
            "Retrying HTTP request after exception",
            extra={"attempt": retry_state.attempt_number},
        )


class AsyncHTTP:
    """Wrapper around :class:`httpx.AsyncClient` with shared retry policy."""

    def __init__(
        self,
        *,
        base_url: Optional[str] = None,
        headers: Optional[Mapping[str, str]] = None,
        timeout: Optional[float] = None,
        follow_redirects: bool = True,
    ) -> None:
        total_timeout = timeout or DEFAULT_TOTAL_TIMEOUT
        self._client = httpx.AsyncClient(
            base_url=base_url or "",
            headers=dict(headers or {}),
            timeout=httpx.Timeout(
                total_timeout,
                connect=DEFAULT_CONNECT_TIMEOUT,
                read=DEFAULT_READ_TIMEOUT,
            ),
            follow_redirects=follow_redirects,
        )

    async def aclose(self) -> None:
        await self._client.aclose()

    @retry(
        reraise=True,
        stop=stop_after_attempt(DEFAULT_MAX_ATTEMPTS),
        # Jittered exponential backoff using Tenacity's built-in helper
        wait=wait_random_exponential(
            multiplier=INITIAL_BACKOFF_SECONDS, max=MAX_BACKOFF_SECONDS
        ),
        retry=retry_if_exception_type(httpx.HTTPError),
        before=_log_retry,
    )
    async def request(
        self,
        method: str,
        url: str,
        *,
        params: Optional[Mapping[str, Any]] = None,
        json: Optional[Any] = None,
        data: Optional[Any] = None,
        headers: Optional[Mapping[str, str]] = None,
        timeout: Optional[float] = None,
    ) -> httpx.Response:
        logger.debug("AsyncHTTP request", extra={"method": method, "url": url})
        response = await self._client.request(
            method,
            url,
            params=params,
            json=json,
            headers=headers,
            timeout=timeout,
            data=data,
        )
        return response

    async def get(self, url: str, **kw: Any) -> httpx.Response:
        return await self.request("GET", url, **kw)

    async def post(self, url: str, **kw: Any) -> httpx.Response:
        return await self.request("POST", url, **kw)

    async def patch(self, url: str, **kw: Any) -> httpx.Response:
        return await self.request("PATCH", url, **kw)

    async def delete(self, url: str, **kw: Any) -> httpx.Response:
        return await self.request("DELETE", url, **kw)


def run_async(coro):
    """Execute an async coroutine from synchronous code."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        raise RuntimeError(
            "Cannot run coroutine synchronously while an event loop is running"
        )
    return asyncio.run(coro)
