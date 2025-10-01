from __future__ import annotations

from typing import Dict, List

import pytest

from config.config import Settings
from integration.hubspot_integration import HubSpotIntegration
from utils.async_http import run_async


class DummyResponse:
    def __init__(self, payload: Dict[str, object]):
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> Dict[str, object]:
        return self._payload


@pytest.fixture(autouse=True)
def clear_settings_cache(monkeypatch):
    monkeypatch.delenv("HUBSPOT_ACCESS_TOKEN", raising=False)
    monkeypatch.delenv("HUBSPOT_CLIENT_SECRET", raising=False)
    monkeypatch.delenv("HUBSPOT_API_BASE_URL", raising=False)
    monkeypatch.delenv("HUBSPOT_REQUEST_TIMEOUT", raising=False)
    monkeypatch.delenv("HUBSPOT_MAX_RETRIES", raising=False)
    monkeypatch.delenv("HUBSPOT_RETRY_BACKOFF_SECONDS", raising=False)


@pytest.fixture
def configured_settings(monkeypatch) -> Settings:
    monkeypatch.setenv("HUBSPOT_ACCESS_TOKEN", "token-123")
    monkeypatch.setenv("HUBSPOT_CLIENT_SECRET", "secret-xyz")
    monkeypatch.setenv("HUBSPOT_API_BASE_URL", "https://api.test.local")
    monkeypatch.setenv("HUBSPOT_REQUEST_TIMEOUT", "5")
    monkeypatch.setenv("HUBSPOT_MAX_RETRIES", "3")
    monkeypatch.setenv("HUBSPOT_RETRY_BACKOFF_SECONDS", "0")
    return Settings()


def test_find_company_by_domain_normalizes_and_matches(monkeypatch, configured_settings):
    integration = HubSpotIntegration(settings=configured_settings)

    captured_payloads: List[dict] = []
    response_payload = {
        "results": [
            {
                "id": "1",
                "properties": {"domain": "Example.COM", "name": "Example"},
            }
        ]
    }

    async def fake_post(path, json=None):
        assert path == integration.SEARCH_PATH
        captured_payloads.append(json)
        filters = json["filterGroups"][0]["filters"][0]
        assert filters["value"] == "example.com"
        return DummyResponse(response_payload)

    monkeypatch.setattr(integration._http, "post", fake_post)

    result = run_async(integration.find_company_by_domain_async("HTTPS://Example.com/"))

    assert result == response_payload["results"][0]
    assert captured_payloads, "Expected HubSpot request payload to be captured"


def test_list_similar_companies_uses_normalized_name(monkeypatch, configured_settings):
    integration = HubSpotIntegration(settings=configured_settings)

    response_payload = {
        "results": [
            {"id": "1", "properties": {"name": "Acme Corp"}},
            {"id": "2", "properties": {"name": "The ACME Corporation"}},
        ]
    }

    async def fake_post(path, json=None):
        filters = json["filterGroups"][0]["filters"][0]
        assert filters["value"] == "acme corporation"
        return DummyResponse(response_payload)

    monkeypatch.setattr(integration._http, "post", fake_post)

    companies = run_async(integration.list_similar_companies(" Acme Corporation "))

    assert len(companies) == 2
    assert companies[0]["id"] == "1"


def test_missing_access_token_raises_error(monkeypatch):
    monkeypatch.delenv("HUBSPOT_ACCESS_TOKEN", raising=False)

    with pytest.raises(EnvironmentError):
        HubSpotIntegration(settings=Settings())
