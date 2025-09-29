import json
from io import BytesIO
from typing import List
from urllib.error import URLError

import pytest

from config.config import Settings
from integration.hubspot_integration import HubSpotIntegration


class FakeResponse(BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.close()
        return False


@pytest.fixture(autouse=True)
def clear_settings_cache(monkeypatch):
    # Ensure a clean environment for each test case.
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
    # Recreate Settings so new environment values are used.
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

    def fake_urlopen(req, timeout):
        assert timeout == configured_settings.hubspot_request_timeout
        assert req.full_url == "https://api.test.local/crm/v3/objects/companies/search"
        assert req.headers["Authorization"] == "Bearer token-123"
        payload = json.loads(req.data.decode("utf-8"))
        captured_payloads.append(payload)
        filters = payload["filterGroups"][0]["filters"][0]
        assert filters["value"] == "example.com"
        return FakeResponse(json.dumps(response_payload).encode("utf-8"))

    monkeypatch.setattr(
        "integration.hubspot_integration.request.urlopen",
        fake_urlopen,
    )

    result = integration.find_company_by_domain("HTTPS://Example.com/")

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

    def fake_urlopen(req, timeout):
        payload = json.loads(req.data.decode("utf-8"))
        filters = payload["filterGroups"][0]["filters"][0]
        assert filters["value"] == "acme corporation"
        return FakeResponse(json.dumps(response_payload).encode("utf-8"))

    monkeypatch.setattr(
        "integration.hubspot_integration.request.urlopen",
        fake_urlopen,
    )

    companies = integration.list_similar_companies(" Acme Corporation ")

    assert len(companies) == 2
    assert companies[0]["id"] == "1"


def test_retry_logic_recovers_from_transient_error(monkeypatch, configured_settings):
    integration = HubSpotIntegration(settings=configured_settings)

    attempts = {"count": 0}

    response_payload = {"results": []}

    def fake_urlopen(req, timeout):
        attempts["count"] += 1
        if attempts["count"] == 1:
            raise URLError("temporary outage")
        return FakeResponse(json.dumps(response_payload).encode("utf-8"))

    monkeypatch.setattr(
        "integration.hubspot_integration.request.urlopen",
        fake_urlopen,
    )

    companies = integration.list_similar_companies("Example")

    assert companies == []
    assert attempts["count"] == 2


def test_missing_access_token_raises_error(monkeypatch):
    monkeypatch.delenv("HUBSPOT_ACCESS_TOKEN", raising=False)

    with pytest.raises(EnvironmentError):
        HubSpotIntegration(settings=Settings())

