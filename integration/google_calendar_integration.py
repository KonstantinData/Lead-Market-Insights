"""Integration helpers for interacting with Google Calendar."""

from __future__ import annotations

import asyncio
import warnings
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Sequence, Union
from urllib import parse

from config.config import Settings
from utils.async_http import AsyncHTTP


@dataclass
class OAuthCredentials:
    """Container for OAuth client configuration."""

    client_id: str
    client_secret: str
    refresh_token: str
    token_uri: str
    token: Optional[str] = None


TimeInput = Union[datetime, str]


class GoogleCalendarIntegration:
    """High-level Google Calendar integration with async HTTP support."""

    DEFAULT_SCOPE: str = "https://www.googleapis.com/auth/calendar.readonly"

    def __init__(
        self,
        credentials: Optional[Dict[str, str]] = None,
        *,
        calendar_id: Optional[str] = None,
        scopes: Optional[Sequence[str]] = None,
        request_timeout: int = 10,
        token_leeway: int = 60,
        settings: Optional[Settings] = None,
    ) -> None:
        self._settings = settings or Settings()
        self.scopes = tuple(scopes) if scopes else (self.DEFAULT_SCOPE,)
        self.calendar_id = calendar_id or self._settings.google_calendar_id
        self._credentials = self._prepare_credentials(credentials)
        self.request_timeout = request_timeout
        self.token_leeway = max(token_leeway, 0)
        self._access_token: Optional[str] = self._credentials.token
        self._token_expiry: Optional[datetime] = None
        self.cal_lookahead_days = self._settings.cal_lookahead_days
        self.cal_lookback_days = self._settings.cal_lookback_days

        self._calendar_http = AsyncHTTP(
            base_url=self._settings.google_api_base_url,
            timeout=float(self.request_timeout),
        )
        self._token_http = AsyncHTTP(timeout=float(self.request_timeout))

    # ------------------------------------------------------------------
    # Credential helpers
    # ------------------------------------------------------------------
    def _prepare_credentials(
        self, credentials: Optional[Dict[str, str]]
    ) -> OAuthCredentials:
        if credentials is None:
            credentials = self._load_credentials_from_env()

        required_keys = {"client_id", "client_secret", "refresh_token", "token_uri"}
        missing = [
            key
            for key in required_keys
            if key not in credentials or not credentials[key]
        ]
        if missing:
            raise EnvironmentError(
                "Missing required Google OAuth credentials: "
                + ", ".join(sorted(missing))
            )

        return OAuthCredentials(
            client_id=credentials["client_id"],
            client_secret=credentials["client_secret"],
            refresh_token=credentials["refresh_token"],
            token_uri=credentials["token_uri"],
            token=credentials.get("token"),
        )

    def _load_credentials_from_env(self) -> Dict[str, str]:
        """Load OAuth credentials from environment variables."""

        credentials = dict(self._settings.google_oauth_credentials)

        if redirect_uris := credentials.get("redirect_uris"):
            credentials["redirect_uris"] = self._parse_redirect_uris(redirect_uris)

        return credentials

    @staticmethod
    def _parse_redirect_uris(raw_value: str) -> Sequence[str]:
        """Return a cleaned list of redirect URIs."""

        return tuple(uri.strip() for uri in raw_value.split(",") if uri.strip())

    # ------------------------------------------------------------------
    # Access token helpers
    # ------------------------------------------------------------------
    async def _ensure_access_token_async(self) -> None:
        token_expired = False
        if self._token_expiry is not None:
            token_expired = datetime.now(timezone.utc) >= self._token_expiry

        if not self._access_token or token_expired:
            await self._refresh_access_token_async()

    async def _refresh_access_token_async(self) -> None:
        payload = parse.urlencode(
            {
                "client_id": self._credentials.client_id,
                "client_secret": self._credentials.client_secret,
                "refresh_token": self._credentials.refresh_token,
                "grant_type": "refresh_token",
            }
        )

        response = await self._token_http.post(
            self._credentials.token_uri,
            data=payload,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        response.raise_for_status()
        token_payload = response.json()

        access_token = token_payload.get("access_token")
        if not access_token:
            raise RuntimeError("Google OAuth response did not include an access token")

        expires_in = token_payload.get("expires_in")
        expiry: Optional[datetime] = None
        if expires_in:
            expiry = datetime.now(timezone.utc) + timedelta(seconds=int(expires_in))
            expiry -= timedelta(seconds=self.token_leeway)

        self._access_token = access_token
        self._token_expiry = expiry

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    async def fetch_events_async(
        self,
        start_time: TimeInput,
        end_time: TimeInput,
        *,
        max_results: Optional[int] = None,
        query: Optional[str] = None,
    ) -> List[dict]:
        await self._ensure_access_token_async()
        return await self._list_events_async(
            start_time=start_time,
            end_time=end_time,
            max_results=max_results,
            query=query,
            single_events=True,
            order_by="startTime",
        )

    def fetch_events(
        self,
        start_time: TimeInput,
        end_time: TimeInput,
        *,
        max_results: Optional[int] = None,
        query: Optional[str] = None,
    ) -> List[dict]:
        warnings.warn(
            "GoogleCalendarIntegration.fetch_events is deprecated; use fetch_events_async instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        raise RuntimeError(
            "GoogleCalendarIntegration.fetch_events is no longer supported. Use fetch_events_async instead."
        )

    async def list_events_async(
        self,
        *,
        max_results: int = 20,
        time_min: Optional[datetime] = None,
        time_max: Optional[datetime] = None,
        query: Optional[str] = None,
        single_events: bool = True,
        order_by: str = "startTime",
    ) -> List[dict]:
        await self._ensure_access_token_async()

        if time_min is None:
            time_min = datetime.now(timezone.utc)

        return await self._list_events_async(
            start_time=time_min,
            end_time=time_max,
            max_results=max_results,
            query=query,
            single_events=single_events,
            order_by=order_by,
        )

    def list_events(
        self,
        *,
        max_results: int = 20,
        time_min: Optional[datetime] = None,
        time_max: Optional[datetime] = None,
        query: Optional[str] = None,
        single_events: bool = True,
        order_by: str = "startTime",
    ) -> List[dict]:
        warnings.warn(
            "GoogleCalendarIntegration.list_events is deprecated; use list_events_async instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        raise RuntimeError(
            "GoogleCalendarIntegration.list_events is no longer supported. Use list_events_async instead."
        )

    async def get_access_token_async(self) -> str:
        await self._ensure_access_token_async()
        if not self._access_token:
            raise RuntimeError("Google OAuth access token is not available")
        return self._access_token

    def get_access_token(self) -> str:
        warnings.warn(
            "GoogleCalendarIntegration.get_access_token is deprecated; use get_access_token_async instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        raise RuntimeError(
            "GoogleCalendarIntegration.get_access_token is no longer supported. Use get_access_token_async instead."
        )

    async def iter_all_events_async(self, time_min: str, time_max: str) -> List[dict]:
        await self._ensure_access_token_async()
        all_events: List[dict] = []
        page_token: Optional[str] = None

        while True:
            page = await self.fetch_events_page_async(
                time_min=time_min,
                time_max=time_max,
                page_token=page_token,
            )
            all_events.extend(page.get("items", []))
            page_token = page.get("nextPageToken")
            if not page_token:
                break

        return all_events

    async def fetch_events_page_async(
        self,
        *,
        time_min: str,
        time_max: str,
        page_token: Optional[str] = None,
        max_results: int = 2500,
    ) -> Dict[str, object]:
        token = await self.get_access_token_async()
        headers = {"Authorization": f"Bearer {token}"}
        params = {
            "timeMin": time_min,
            "timeMax": time_max,
            "singleEvents": "true",
            "orderBy": "startTime",
            "maxResults": max_results,
        }
        if page_token:
            params["pageToken"] = page_token

        calendar_encoded = parse.quote(self.calendar_id, safe="@")
        response = await self._calendar_http.get(
            f"/calendar/v3/calendars/{calendar_encoded}/events",
            params=params,
            headers=headers,
        )
        response.raise_for_status()
        return response.json()

    async def _list_events_async(
        self,
        *,
        start_time: Optional[TimeInput],
        end_time: Optional[TimeInput],
        max_results: Optional[int],
        query: Optional[str],
        single_events: bool,
        order_by: str,
    ) -> List[dict]:
        parameters = {
            "singleEvents": "true" if single_events else "false",
            "orderBy": order_by,
        }

        if max_results is not None:
            parameters["maxResults"] = max_results

        if start_time is not None:
            parameters["timeMin"] = self._normalize_time_input(start_time)

        if end_time is not None:
            parameters["timeMax"] = self._normalize_time_input(end_time)

        if query:
            parameters["q"] = query

        token = await self.get_access_token_async()
        headers = {"Authorization": f"Bearer {token}"}

        calendar_encoded = parse.quote(self.calendar_id, safe="@")
        response = await self._calendar_http.get(
            f"/calendar/v3/calendars/{calendar_encoded}/events",
            params=parameters,
            headers=headers,
        )
        response.raise_for_status()
        payload = response.json()
        events = payload.get("items", [])
        return events

    async def aclose(self) -> None:
        await asyncio.gather(
            self._calendar_http.aclose(),
            self._token_http.aclose(),
        )

    @staticmethod
    def _normalize_time_input(value: TimeInput) -> str:
        if isinstance(value, datetime):
            return GoogleCalendarIntegration._to_rfc3339(value)
        if isinstance(value, str):
            return value
        raise TypeError("start_time and end_time must be datetime or RFC3339 string")

    @staticmethod
    def _to_rfc3339(moment: datetime) -> str:
        """Return a RFC 3339 compliant timestamp."""

        if moment.tzinfo is None:
            moment = moment.replace(tzinfo=timezone.utc)
        else:
            moment = moment.astimezone(timezone.utc)

        return moment.isoformat()
