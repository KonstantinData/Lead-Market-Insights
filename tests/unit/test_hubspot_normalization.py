"""Unit tests for HubSpot CRM domain normalisation helpers."""

from __future__ import annotations

from typing import Any, Mapping

import pytest

from integration.hubspot_integration import HubSpotIntegration


@pytest.fixture()
def hubspot_integration() -> HubSpotIntegration:
    """Provide a HubSpot integration instance with explicit runtime config."""

    return HubSpotIntegration(
        access_token="test-token",
        api_base_url="https://api.example.com",
        request_timeout=5,
        max_retries=1,
        retry_backoff_seconds=0.0,
    )


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("Example.COM", "example.com"),
        ("https://www.example.com", "example.com"),
        ("HTTP://example.com/path", "example.com"),
        ("//www.example.org/resource", "example.org"),
        ("   subdomain.example.io   ", "subdomain.example.io"),
        ("", ""),
        ("   ", ""),
    ],
)
def test_normalise_domain_variants(
    hubspot_integration: HubSpotIntegration, raw: str, expected: str
) -> None:
    """The helper strips schemes, prefixes, and whitespace consistently."""

    assert hubspot_integration._normalise_domain(raw) == expected


@pytest.mark.parametrize(
    "properties,expected",
    [
        ({"domain": "Example.COM", "website": "ignored"}, "example.com"),
        ({"website": "https://sub.example.net"}, "https://sub.example.net"),
        ({"domain": ""}, ""),
        ({}, ""),
    ],
)
def test_extract_domain_prefers_primary_field(
    hubspot_integration: HubSpotIntegration, properties: Mapping[str, Any], expected: str
) -> None:
    """Domain extraction falls back across known HubSpot property names."""

    company = {"properties": dict(properties)}
    assert hubspot_integration._extract_domain(company) == expected


def test_extract_domain_handles_non_mapping_payload(
    hubspot_integration: HubSpotIntegration,
) -> None:
    """Non-mapping inputs yield an empty string rather than raising."""

    assert hubspot_integration._extract_domain({"properties": None}) == ""
    assert hubspot_integration._extract_domain({}) == ""
