"""Integration helpers for interacting with Google Calendar."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Union
from urllib import parse, request
from urllib.error import HTTPError, URLError
from datetime import datetime, timedelta, timezone  # <--- HIER: timezone ergänzt!

from config.config import Settings


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
    """
    High-level Google Calendar integration.
    Public methods (e.g. fetch_events) handle authentication and token refresh internally.
    Private members (e.g. _access_token, _ensure_access_token) are implementation details.
    """

    DEFAULT_SCOPE: str = "https://www.googleapis.com/auth/calendar.readonly"
    GOOGLE_CALENDAR_API_URL: str = "https://www.googleapis.com/calendar/v3"

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
    def _ensure_access_token(self) -> None:
        token_expired = False
        if self._token_expiry is not None:
            token_expired = datetime.now(timezone.utc) >= self._token_expiry

        if not self._access_token or token_expired:
            self._refresh_access_token()

    def _refresh_access_token(self) -> None:
        logging.debug("Refreshing Google Calendar access token")
        payload = parse.urlencode(
            {
                "client_id": self._credentials.client_id,
                "client_secret": self._credentials.client_secret,
                "refresh_token": self._credentials.refresh_token,
                "grant_type": "refresh_token",
            }
        ).encode("utf-8")

        token_request = request.Request(
            self._credentials.token_uri,
            data=payload,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )

        try:
            with request.urlopen(
                token_request, timeout=self.request_timeout
            ) as response:
                token_payload = json.load(response)
        except HTTPError as exc:  # pragma: no cover - network interaction
            logging.error("Google OAuth token refresh failed: %s", exc)
            raise
        except URLError as exc:  # pragma: no cover - network interaction
            logging.error("Unable to reach Google OAuth token endpoint: %s", exc)
            raise

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
    def fetch_events(
        self,
        start_time: TimeInput,
        end_time: TimeInput,
        *,
        max_results: Optional[int] = None,
        query: Optional[str] = None,
    ) -> List[dict]:
        """
        Public facade: ensures token validity and fetches events.

        Args:
            start_time (datetime|str): RFC3339 string or datetime (will be normalized internally).
            end_time (datetime|str): RFC3339 string or datetime.
            max_results (int|None): optional limit.
            query (str|None): optional search query.

        Returns:
            list[dict]: Calendar events.
        """

        self._ensure_access_token()
        return self._list_events(
            start_time=start_time,
            end_time=end_time,
            max_results=max_results,
            query=query,
            single_events=True,
            order_by="startTime",
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
        """Return events from the configured Google Calendar."""

        self._ensure_access_token()

        if time_min is None:
            time_min = datetime.now(timezone.utc)

        return self._list_events(
            start_time=time_min,
            end_time=time_max,
            max_results=max_results,
            query=query,
            single_events=single_events,
            order_by=order_by,
        )

    def get_access_token(self) -> str:
        """Return a valid OAuth access token, refreshing it if necessary."""

        self._ensure_access_token()
        if not self._access_token:
            raise RuntimeError("Google OAuth access token is not available")
        return self._access_token

    def _authorized_request(self, url: str) -> Dict[str, object]:
        request_obj = request.Request(
            url,
            headers={"Authorization": f"Bearer {self._access_token}"},
        )

        with request.urlopen(request_obj, timeout=self.request_timeout) as response:
            return json.load(response)

    def _list_events(
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

        encoded_params = parse.urlencode(parameters)
        calendar_encoded = parse.quote(self.calendar_id, safe="@")
        url = (
            f"{self.GOOGLE_CALENDAR_API_URL}/calendars/{calendar_encoded}/events?{encoded_params}"
        )

        logging.info("Listing Google Calendar events from '%s'", self.calendar_id)

        try:
            response = self._authorized_request(url)
        except HTTPError as exc:  # pragma: no cover - network interaction
            logging.error("Error listing events from Google Calendar: %s", exc)
            raise
        except URLError as exc:  # pragma: no cover - network interaction
            logging.error("Unable to reach Google Calendar API: %s", exc)
            raise

        events = response.get("items", [])
        logging.debug("Retrieved %d Google Calendar events", len(events))
        return events

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
