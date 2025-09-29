"""HubSpot CRM integration helpers for company lookup workflows."""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Sequence
from urllib import request
from urllib.error import HTTPError, URLError

from config.config import Settings
from utils.text_normalization import normalize_text


@dataclass
class HubSpotConfig:
    """Runtime configuration for :class:`HubSpotIntegration`."""

    access_token: str
    client_secret: Optional[str]
    api_base_url: str
    request_timeout: int
    max_retries: int
    retry_backoff_seconds: float


class HubSpotIntegration:
    """Wrapper around HubSpot's CRM API for company discovery."""

    SEARCH_PATH: str = "/crm/v3/objects/companies/search"

    def __init__(
        self,
        *,
        settings: Optional[Settings] = None,
        access_token: Optional[str] = None,
        client_secret: Optional[str] = None,
        api_base_url: Optional[str] = None,
        request_timeout: Optional[int] = None,
        max_retries: Optional[int] = None,
        retry_backoff_seconds: Optional[float] = None,
    ) -> None:
        runtime_settings = settings or Settings()

        resolved_access_token = access_token or runtime_settings.hubspot_access_token
        if not resolved_access_token:
            raise EnvironmentError("HubSpot access token is not configured.")

        resolved_base_url = api_base_url or runtime_settings.hubspot_api_base_url
        if not resolved_base_url:
            raise EnvironmentError("HubSpot API base URL is not configured.")

        resolved_timeout = request_timeout or runtime_settings.hubspot_request_timeout
        resolved_retries = max_retries or runtime_settings.hubspot_max_retries
        resolved_backoff = (
            retry_backoff_seconds or runtime_settings.hubspot_retry_backoff_seconds
        )

        self._config = HubSpotConfig(
            access_token=resolved_access_token,
            client_secret=client_secret or runtime_settings.hubspot_client_secret,
            api_base_url=resolved_base_url.rstrip("/"),
            request_timeout=resolved_timeout,
            max_retries=max(1, resolved_retries),
            retry_backoff_seconds=max(0.0, resolved_backoff),
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def find_company_by_domain(
        self,
        domain: str,
        *,
        properties: Optional[Sequence[str]] = None,
    ) -> Optional[Dict[str, object]]:
        """Return the HubSpot company that owns ``domain`` if available."""

        normalised_input = normalize_text(domain)
        normalised_domain = self._normalise_domain(normalised_input)
        if not normalised_domain:
            return None

        payload = {
            "filterGroups": [
                {
                    "filters": [
                        {
                            "propertyName": "domain",
                            "operator": "EQ",
                            "value": normalised_domain,
                        }
                    ]
                }
            ],
            "limit": 5,
        }

        if properties:
            payload["properties"] = list(properties)

        response_payload = self._post(self.SEARCH_PATH, payload)
        results: Iterable[Dict[str, object]] = response_payload.get("results", [])

        for company in results:
            domain_value = self._extract_domain(company)
            if domain_value and self._normalise_domain(domain_value) == normalised_domain:
                return company

        return next(iter(results), None)

    def list_similar_companies(
        self,
        company_name: str,
        *,
        limit: int = 5,
        properties: Optional[Sequence[str]] = None,
    ) -> List[Dict[str, object]]:
        """Return companies whose names resemble ``company_name``."""

        normalised_name = normalize_text(company_name)
        if not normalised_name:
            return []

        payload = {
            "filterGroups": [
                {
                    "filters": [
                        {
                            "propertyName": "name",
                            "operator": "CONTAINS_TOKEN",
                            "value": normalised_name,
                        }
                    ]
                }
            ],
            "limit": max(1, limit),
        }

        if properties:
            payload["properties"] = list(properties)

        response_payload = self._post(self.SEARCH_PATH, payload)
        results: Iterable[Dict[str, object]] = response_payload.get("results", [])
        return list(results)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _post(self, path: str, payload: Dict[str, object]) -> Dict[str, object]:
        url = f"{self._config.api_base_url}{path}"
        body = json.dumps(payload).encode("utf-8")
        headers = {
            "Authorization": f"Bearer {self._config.access_token}",
            "Content-Type": "application/json",
        }

        req = request.Request(url, data=body, headers=headers, method="POST")

        for attempt in range(1, self._config.max_retries + 1):
            try:
                logging.info(
                    "HubSpot API request",
                    extra={
                        "method": "POST",
                        "url": url,
                        "attempt": attempt,
                    },
                )
            except TypeError:
                logging.info("HubSpot API request %s %s (attempt %d)", "POST", url, attempt)

            try:
                with request.urlopen(req, timeout=self._config.request_timeout) as resp:
                    raw = resp.read()
                    return json.loads(raw.decode("utf-8")) if raw else {}
            except HTTPError as exc:
                logging.error(
                    "HubSpot API responded with HTTP error: %s",
                    exc,
                )
                if attempt == self._config.max_retries:
                    raise
            except URLError as exc:
                logging.error("Unable to reach HubSpot API: %s", exc)
                if attempt == self._config.max_retries:
                    raise

            self._backoff(attempt)

        return {}

    def _backoff(self, attempt: int) -> None:
        delay = self._config.retry_backoff_seconds * (2 ** (attempt - 1))
        if delay > 0:
            time.sleep(delay)

    @staticmethod
    def _normalise_domain(value: str) -> str:
        text = normalize_text(value)
        if not text:
            return ""

        stripped = text
        if "//" in stripped:
            stripped = stripped.split("//", 1)[1]
        stripped = stripped.split("/", 1)[0]
        if stripped.startswith("www."):
            stripped = stripped[4:]
        return stripped

    @staticmethod
    def _extract_domain(company: Dict[str, object]) -> str:
        properties = company.get("properties") if isinstance(company, dict) else None
        if isinstance(properties, dict):
            for key in ("domain", "website"):
                value = properties.get(key)
                if value:
                    return normalize_text(value)
        return ""

