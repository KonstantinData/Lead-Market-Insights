from __future__ import annotations
from datetime import datetime, timedelta, timezone
from typing import Dict

import pytest

from integration.google_calendar_integration import GoogleCalendarIntegration


class DummyResponse:
    def __init__(self, payload: Dict[str, object]):
        self._payload = payload

    def raise_for_status(self) -> None:  # pragma: no cover - simple stub
        return None

    def json(self) -> Dict[str, object]:
        return self._payload


@pytest.fixture
def base_credentials() -> Dict[str, str]:
    return {
        "client_id": "client",
        "client_secret": "secret",
        "refresh_token": "refresh",
        "token_uri": "https://example.com/token",
    }


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def test_init_without_required_env(monkeypatch):
    for key in (
        "GOOGLE_CLIENT_ID",
        "GOOGLE_CLIENT_SECRET",
        "GOOGLE_REFRESH_TOKEN",
        "GOOGLE_TOKEN_URI",
    ):
        monkeypatch.delenv(key, raising=False)

    with pytest.raises(EnvironmentError):
        GoogleCalendarIntegration()


@pytest.mark.anyio("asyncio")
async def test_refresh_access_token_async(monkeypatch, base_credentials):
    integration = GoogleCalendarIntegration(credentials=base_credentials)
    response_payload = {"access_token": "new-token", "expires_in": 3600}

    async def fake_post(url, data=None, headers=None):
        assert url == base_credentials["token_uri"]
        body = dict(item.split("=") for item in data.split("&"))
        assert body["client_id"] == base_credentials["client_id"]
        assert body["client_secret"] == base_credentials["client_secret"]
        assert body["refresh_token"] == base_credentials["refresh_token"]
        assert headers["Content-Type"] == "application/x-www-form-urlencoded"
        return DummyResponse(response_payload)

    monkeypatch.setattr(integration._token_http, "post", fake_post)

    await integration._refresh_access_token_async()

    assert integration._access_token == "new-token"
    assert integration._token_expiry is not None
    assert integration._token_expiry > datetime.now(timezone.utc)


@pytest.mark.anyio("asyncio")
async def test_list_events_async_uses_authorized_request(mocker, base_credentials):
    credentials = {**base_credentials, "token": "existing"}
    integration = GoogleCalendarIntegration(credentials=credentials)
    integration._token_expiry = datetime.now(timezone.utc) + timedelta(hours=1)

    mocked_response = DummyResponse({"items": [{"id": "1"}]})
    integration._calendar_http.get = mocker.AsyncMock(return_value=mocked_response)

    events = await integration.list_events_async(max_results=5)

    integration._calendar_http.get.assert_awaited_once()
    call_kwargs = integration._calendar_http.get.call_args.kwargs
    assert call_kwargs["params"]["maxResults"] == 5
    assert call_kwargs["headers"]["Authorization"] == "Bearer existing"
    assert events == [{"id": "1"}]


@pytest.mark.anyio("asyncio")
async def test_fetch_events_async_delegates_to_list(mocker, base_credentials):
    integration = GoogleCalendarIntegration(credentials=base_credentials)

    mocker.patch.object(integration, "_ensure_access_token_async")
    integration._list_events_async = mocker.AsyncMock(return_value=[{"id": "evt_1"}])

    events = await integration.fetch_events_async(
        "2025-01-01T00:00:00Z",
        "2025-01-02T00:00:00Z",
    )

    integration._ensure_access_token_async.assert_awaited_once()
    integration._list_events_async.assert_awaited_once_with(
        start_time="2025-01-01T00:00:00Z",
        end_time="2025-01-02T00:00:00Z",
        max_results=None,
        query=None,
        single_events=True,
        order_by="startTime",
    )
    assert events == [{"id": "evt_1"}]


def test_parse_redirect_uris():
    raw_value = (
        "https://a.example/return, https://b.example/return, ,https://c.example/return"
    )
    parsed = GoogleCalendarIntegration._parse_redirect_uris(raw_value)
    assert parsed == (
        "https://a.example/return",
        "https://b.example/return",
        "https://c.example/return",
    )
