"""Read-only integration for Google Contacts using the People API."""

from __future__ import annotations

from typing import Dict, List, Optional

import warnings

from utils.async_http import AsyncHTTP


class GoogleContactsIntegration:
    """Read-only integration for Google Contacts using People API."""

    PEOPLE_API_URL = "https://people.googleapis.com"

    def __init__(self, access_token: str, request_timeout: int = 10):
        self.access_token = access_token
        self.request_timeout = request_timeout
        self._http = AsyncHTTP(
            base_url=self.PEOPLE_API_URL,
            timeout=float(request_timeout),
        )

    async def list_contacts_async(
        self,
        *,
        page_size: int = 10,
        person_fields: str = "names,emailAddresses",
        page_token: Optional[str] = None,
    ) -> List[Dict[str, object]]:
        params = {"pageSize": page_size, "personFields": person_fields}
        if page_token:
            params["pageToken"] = page_token

        headers = {"Authorization": f"Bearer {self.access_token}"}
        response = await self._http.get(
            "/v1/people/me/connections", params=params, headers=headers
        )
        response.raise_for_status()
        payload = response.json()
        return payload.get("connections", [])

    def list_contacts(
        self,
        page_size: int = 10,
        person_fields: str = "names,emailAddresses",
        page_token: Optional[str] = None,
    ) -> List[Dict[str, object]]:
        warnings.warn(
            "GoogleContactsIntegration.list_contacts is deprecated; use list_contacts_async instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        raise RuntimeError(
            "GoogleContactsIntegration.list_contacts is no longer supported. Use list_contacts_async instead."
        )

    async def aclose(self) -> None:
        await self._http.aclose()
