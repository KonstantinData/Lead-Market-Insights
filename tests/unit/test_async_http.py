"""Unit tests for the async HTTP wrapper and retry behaviour."""

from __future__ import annotations

import httpx
import pytest
from tenacity import wait_fixed

from utils.async_http import AsyncHTTP


pytestmark = pytest.mark.asyncio


async def test_async_http_retries_on_http_error(monkeypatch, caplog):
    client = AsyncHTTP()
    request = httpx.Request("GET", "https://example.com")
    failures = [
        httpx.RequestError("boom", request=request),
        httpx.Response(200, request=request),
    ]
    call_count = 0

    async def fake_request(method, url, **kwargs):
        nonlocal call_count
        call_count += 1
        response = failures[call_count - 1]
        if isinstance(response, httpx.Response):
            return response
        raise response

    monkeypatch.setattr(client._client, "request", fake_request)
    monkeypatch.setattr(AsyncHTTP.request.retry, "wait", wait_fixed(0))

    with caplog.at_level("WARNING"):
        response = await client.get("/resource")

    assert response.status_code == 200
    assert call_count == 2
    assert any("Retrying HTTP request" in record.message for record in caplog.records)

    await client.aclose()
