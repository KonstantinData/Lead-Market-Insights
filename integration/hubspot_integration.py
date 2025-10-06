"""HubSpot CRM integration helpers for company lookup workflows."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence

from config.config import Settings
import warnings

from utils import concurrency
from utils.async_http import AsyncHTTP
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
        self._http = AsyncHTTP(
            base_url=self._config.api_base_url,
            headers={
                "Authorization": f"Bearer {self._config.access_token}",
                "Content-Type": "application/json",
            },
            timeout=float(self._config.request_timeout),
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    async def find_company_by_domain_async(
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

        response_payload = await self._post(self.SEARCH_PATH, payload)
        results: Iterable[Dict[str, object]] = response_payload.get("results", [])

        for company in results:
            domain_value = self._extract_domain(company)
            if (
                domain_value
                and self._normalise_domain(domain_value) == normalised_domain
            ):
                return company

        return next(iter(results), None)

    def find_company_by_domain(
        self,
        domain: str,
        *,
        properties: Optional[Sequence[str]] = None,
    ) -> Optional[Dict[str, object]]:
        warnings.warn(
            "HubSpotIntegration.find_company_by_domain is deprecated; use find_company_by_domain_async instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        raise RuntimeError(
            "HubSpotIntegration.find_company_by_domain is no longer supported. Use find_company_by_domain_async instead."
        )

    async def list_similar_companies(
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

        response_payload = await self._post(self.SEARCH_PATH, payload)
        results: Iterable[Dict[str, object]] = response_payload.get("results", [])
        return list(results)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    async def _post(self, path: str, payload: Dict[str, object]) -> Dict[str, object]:
        timeout = float(self._config.request_timeout)
        async with concurrency.HUBSPOT_SEMAPHORE:
            try:
                response = await asyncio.wait_for(
                    self._http.post(path, json=payload, timeout=timeout),
                    timeout=timeout,
                )
            except asyncio.TimeoutError as exc:
                raise TimeoutError(
                    f"HubSpot request to {path} timed out after {timeout:.2f} seconds"
                ) from exc
        response.raise_for_status()
        return response.json()

    async def lookup_company_with_attachments(
        self,
        domain: str,
        *,
        properties: Optional[Sequence[str]] = None,
        attachment_limit: int = 5,
    ) -> Dict[str, Any]:
        """Return the company record and associated file attachments if available.

        Parameters
        ----------
        domain:
            The company web domain used to locate the HubSpot record.
        properties:
            Optional list of HubSpot company properties to include in the response.
        attachment_limit:
            Upper bound on the number of attachment association records to fetch.

        Returns
        -------
        dict
            ``{"company": <company or None>, "attachments": [..]}``
        """

        company = await self.find_company_by_domain_async(domain, properties=properties)
        if not company:
            return {"company": None, "attachments": []}

        company_id = self._extract_company_id(company)
        if not company_id:
            return {"company": company, "attachments": []}

        attachments = await self._list_company_files(company_id, limit=attachment_limit)
        return {"company": company, "attachments": attachments}

    async def _get(
        self, path: str, *, params: Optional[Mapping[str, Any]] = None
    ) -> Dict[str, Any]:
        timeout = float(self._config.request_timeout)
        async with concurrency.HUBSPOT_SEMAPHORE:
            try:
                response = await asyncio.wait_for(
                    self._http.get(path, params=params, timeout=timeout),
                    timeout=timeout,
                )
            except asyncio.TimeoutError as exc:
                raise TimeoutError(
                    f"HubSpot request to {path} timed out after {timeout:.2f} seconds"
                ) from exc
        if response.status_code == 404:
            return {}
        response.raise_for_status()
        return response.json()

    async def _list_company_files(self, company_id: str, *, limit: int = 5) -> List[Dict[str, Any]]:
        path = f"/crm/v3/objects/companies/{company_id}/associations/files"
        params: Dict[str, Any] = {"limit": max(1, limit)}
        payload = await self._get(path, params=params)
        results = payload.get("results", [])
        attachments: List[Dict[str, Any]] = []
        if isinstance(results, Iterable):
            for item in results:
                if isinstance(item, Mapping):
                    attachments.append(dict(item))
        return attachments

    @staticmethod
    def _extract_company_id(company: Mapping[str, Any]) -> Optional[str]:
        for key in ("id", "companyId", "objectId"):
            value = company.get(key)
            if value:
                return str(value)

        properties = company.get("properties")
        if isinstance(properties, Mapping):
            for key in ("hs_object_id", "id"):
                value = properties.get(key)
                if value:
                    return str(value)
        return None

    async def aclose(self) -> None:
        await self._http.aclose()

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
