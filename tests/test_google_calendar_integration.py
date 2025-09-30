import json
import sys
from datetime import datetime, timedelta, timezone
from io import BytesIO
from pathlib import Path
from typing import Dict

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from integration.google_calendar_integration import GoogleCalendarIntegration


class FakeResponse(BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.close()
        return False


@pytest.fixture
def base_credentials() -> Dict[str, str]:
    return {
        "client_id": "client",
        "client_secret": "secret",
        "refresh_token": "refresh",
        "token_uri": "https://example.com/token",
    }


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


def test_refresh_access_token(monkeypatch, base_credentials):
    integration = GoogleCalendarIntegration(credentials=base_credentials)

    payload = {"access_token": "new-token", "expires_in": 3600}

    def fake_urlopen(req, timeout):
        assert req.full_url == base_credentials["token_uri"]
        body = dict(item.split("=") for item in req.data.decode("utf-8").split("&"))
        assert body["client_id"] == base_credentials["client_id"]
        assert body["client_secret"] == base_credentials["client_secret"]
        assert body["refresh_token"] == base_credentials["refresh_token"]
        assert body["grant_type"] == "refresh_token"
        return FakeResponse(json.dumps(payload).encode("utf-8"))

    monkeypatch.setattr("integration.google_calendar_integration.request.urlopen", fake_urlopen)

    integration._refresh_access_token()

    assert integration._access_token == "new-token"
    assert integration._token_expiry is not None
    assert integration._token_expiry > datetime.now(timezone.utc)


def test_list_events_uses_authorized_request(monkeypatch, base_credentials):
    credentials = {**base_credentials, "token": "existing"}
    integration = GoogleCalendarIntegration(credentials=credentials)
    integration._token_expiry = datetime.now(timezone.utc) + timedelta(hours=1)

    def fake_urlopen(req, timeout):
        assert req.headers["Authorization"] == "Bearer existing"
        assert "maxResults=5" in req.full_url
        response_payload = {"items": [{"id": "1"}]}
        return FakeResponse(json.dumps(response_payload).encode("utf-8"))

    monkeypatch.setattr(
        "integration.google_calendar_integration.request.urlopen",
        fake_urlopen
    )

    events = integration.list_events(max_results=5)

    assert events == [{"id": "1"}]


def test_fetch_events_calls_internal_methods(mocker, base_credentials):
    integration = GoogleCalendarIntegration(credentials=base_credentials)

    mocker.patch.object(integration, "_ensure_access_token")
    mocker.patch.object(integration, "_list_events", return_value=[{"id": "evt_1"}])

    events = integration.fetch_events(
        "2025-01-01T00:00:00Z",
        "2025-01-02T00:00:00Z",
    )

    integration._ensure_access_token.assert_called_once()
    integration._list_events.assert_called_once_with(
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
