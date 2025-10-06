from __future__ import annotations

from typing import Dict, List

import asyncio
import math
import time

import pytest

from config.config import Settings
from integration.hubspot_integration import HubSpotIntegration


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
    monkeypatch.delenv("MAX_CONCURRENT_HUBSPOT", raising=False)
    monkeypatch.delenv("MAX_CONCURRENT_RESEARCH", raising=False)


@pytest.fixture
def configured_settings(monkeypatch) -> Settings:
    monkeypatch.setenv("HUBSPOT_ACCESS_TOKEN", "token-123")
    monkeypatch.setenv("HUBSPOT_CLIENT_SECRET", "secret-xyz")
    monkeypatch.setenv("HUBSPOT_API_BASE_URL", "https://api.test.local")
    monkeypatch.setenv("HUBSPOT_REQUEST_TIMEOUT", "5")
    monkeypatch.setenv("HUBSPOT_MAX_RETRIES", "3")
    monkeypatch.setenv("HUBSPOT_RETRY_BACKOFF_SECONDS", "0")
    return Settings()


@pytest.mark.asyncio
async def test_find_company_by_domain_normalizes_and_matches(
    monkeypatch, configured_settings
):
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

    async def fake_post(path, json=None, timeout=None):
        assert path == integration.SEARCH_PATH
        captured_payloads.append(json)
        filters = json["filterGroups"][0]["filters"][0]
        assert filters["value"] == "example.com"
        return DummyResponse(response_payload)

    monkeypatch.setattr(integration._http, "post", fake_post)

    result = await integration.find_company_by_domain_async("HTTPS://Example.com/")

    assert result == response_payload["results"][0]
    assert captured_payloads, "Expected HubSpot request payload to be captured"


@pytest.mark.asyncio
async def test_list_similar_companies_uses_normalized_name(
    monkeypatch, configured_settings
):
    integration = HubSpotIntegration(settings=configured_settings)

    response_payload = {
        "results": [
            {"id": "1", "properties": {"name": "Acme Corp"}},
            {"id": "2", "properties": {"name": "The ACME Corporation"}},
        ]
    }

    async def fake_post(path, json=None, timeout=None):
        filters = json["filterGroups"][0]["filters"][0]
        assert filters["value"] == "acme corporation"
        return DummyResponse(response_payload)

    monkeypatch.setattr(integration._http, "post", fake_post)

    companies = await integration.list_similar_companies(" Acme Corporation ")

    assert len(companies) == 2
    assert companies[0]["id"] == "1"


def test_missing_access_token_raises_error(monkeypatch):
    monkeypatch.delenv("HUBSPOT_ACCESS_TOKEN", raising=False)

    with pytest.raises(EnvironmentError):
        HubSpotIntegration(settings=Settings())


@pytest.mark.asyncio
async def test_hubspot_requests_respect_concurrency_limit(
    monkeypatch, configured_settings
):
    import utils.concurrency as concurrency

    previous_hubspot = concurrency.HUBSPOT_SEMAPHORE.limit
    previous_research = concurrency.RESEARCH_TASK_SEMAPHORE.limit
    concurrency.reload_limits(hubspot=2, research=previous_research)

    try:
        integration = HubSpotIntegration(settings=configured_settings)

        response_payload = {
            "results": [
                {"id": "1", "properties": {"name": "Acme Corp"}},
            ]
        }

        delay = 0.05

        async def slow_post(path, json=None, timeout=None):
            await asyncio.sleep(delay)
            return DummyResponse(response_payload)

        monkeypatch.setattr(integration._http, "post", slow_post)

        total_requests = 5

        async def run_requests() -> float:
            start = time.perf_counter()
            await asyncio.gather(
                *(
                    integration.list_similar_companies("Acme")
                    for _ in range(total_requests)
                )
            )
            return time.perf_counter() - start

        elapsed = await run_requests()
        expected_batches = math.ceil(
            total_requests / concurrency.HUBSPOT_SEMAPHORE.limit
        )
        expected_min = expected_batches * delay

        assert elapsed >= expected_min - 0.02, (
            f"Expected at least {expected_min:.3f}s but observed {elapsed:.3f}s"
        )
    finally:
        concurrency.reload_limits(hubspot=previous_hubspot, research=previous_research)
