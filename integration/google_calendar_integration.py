"""Integration helpers for interacting with Google Calendar."""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Dict, Iterable, Optional, Sequence
from urllib import parse, request
from urllib.error import HTTPError, URLError

from dotenv import load_dotenv

load_dotenv()


@dataclass
class OAuthCredentials:
    """Container for OAuth client configuration."""

    client_id: str
    client_secret: str
    refresh_token: str
    token_uri: str
    token: Optional[str] = None


class GoogleCalendarIntegration:
    """Interact with Google Calendar via the public REST API."""

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
    ) -> None:
        self.scopes = tuple(scopes) if scopes else (self.DEFAULT_SCOPE,)
        self.calendar_id = calendar_id or os.getenv("GOOGLE_CALENDAR_ID", "primary")
        self._credentials = self._prepare_credentials(credentials)
        self.request_timeout = request_timeout
        self.token_leeway = max(token_leeway, 0)
        self._access_token: Optional[str] = self._credentials.token
        self._token_expiry: Optional[datetime] = None

    # ------------------------------------------------------------------
    # Credential helpers
    # ------------------------------------------------------------------
    def _prepare_credentials(self, credentials: Optional[Dict[str, str]]) -> OAuthCredentials:
        if credentials is None:
            credentials = self._load_credentials_from_env()

        required_keys = {"client_id", "client_secret", "refresh_token", "token_uri"}
        missing = [key for key in required_keys if key not in credentials or not credentials[key]]
        if missing:
            raise EnvironmentError(
                "Missing required Google OAuth credentials: " + ", ".join(sorted(missing))
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

        env_mapping = {
            "client_id": "GOOGLE_CLIENT_ID",
            "client_secret": "GOOGLE_CLIENT_SECRET",
            "refresh_token": "GOOGLE_REFRESH_TOKEN",
            "token_uri": "GOOGLE_TOKEN_URI",
            "token": "GOOGLE_ACCESS_TOKEN",
        }

        credentials = {
            key: value
            for key, env_name in env_mapping.items()
            if (value := os.getenv(env_name))
        }

        optional_env = {
            "auth_uri": "GOOGLE_AUTH_URI",
            "project_id": "GOOGLE_PROJECT_ID",
            "redirect_uris": "GOOGLE_REDIRECT_URIS",
        }

        for key, env_name in optional_env.items():
            value = os.getenv(env_name)
            if value:
                credentials[key] = value

        auth_provider_key = os.getenv("GOOGLE_AUTH_PROVIDER_X509_CERT_URL") or os.getenv(
            "GHOOGLE_AUTH_PROVIDER_X509_CERT_URL"
        )
        if auth_provider_key:
            credentials["auth_provider_x509_cert_url"] = auth_provider_key

        if redirect_uris := credentials.get("redirect_uris"):
            credentials["redirect_uris"] = self._parse_redirect_uris(redirect_uris)

        return credentials

    @staticmethod
    def _parse_redirect_uris(raw_value: str) -> Sequence[str]:
        """Return a cleaned list of redirect URIs."""

        return tuple(
            uri.strip()
            for uri in raw_value.split(",")
            if uri.strip()
        )

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
            with request.urlopen(token_request, timeout=self.request_timeout) as response:
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
    def list_events(
        self,
        *,
        max_results: int = 10,
        time_min: Optional[datetime] = None,
        time_max: Optional[datetime] = None,
        query: Optional[str] = None,
        single_events: bool = True,
        order_by: str = "startTime",
    ) -> Iterable[dict]:
        """Return events from the configured Google Calendar."""

        self._ensure_access_token()

        parameters = {
            "maxResults": max_results,
            "singleEvents": "true" if single_events else "false",
            "orderBy": order_by,
        }

        if time_min is None:
            time_min = datetime.now(timezone.utc)

        parameters["timeMin"] = self._to_rfc3339(time_min)

        if time_max is not None:
            parameters["timeMax"] = self._to_rfc3339(time_max)

        if query:
            parameters["q"] = query

        encoded_params = parse.urlencode(parameters)
        calendar_encoded = parse.quote(self.calendar_id, safe="@")
        url = f"{self.GOOGLE_CALENDAR_API_URL}/calendars/{calendar_encoded}/events?{encoded_params}"

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

    def _authorized_request(self, url: str) -> Dict[str, object]:
        request_obj = request.Request(
            url,
            headers={"Authorization": f"Bearer {self._access_token}"},
        )

        with request.urlopen(request_obj, timeout=self.request_timeout) as response:
            return json.load(response)

    @staticmethod
    def _to_rfc3339(moment: datetime) -> str:
        """Return a RFC 3339 compliant timestamp."""

        if moment.tzinfo is None:
            moment = moment.replace(tzinfo=timezone.utc)
        else:
            moment = moment.astimezone(timezone.utc)

        return moment.isoformat()
