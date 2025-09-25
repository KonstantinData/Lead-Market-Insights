import json
import logging
import os
from urllib import request, parse
from urllib.error import HTTPError, URLError


class GoogleContactsIntegration:
    """Read-only integration for Google Contacts using people API."""

    PEOPLE_API_URL = "https://people.googleapis.com/v1/people/me/connections"

    def __init__(self, access_token: str, request_timeout: int = 10):
        self.access_token = access_token
        self.request_timeout = request_timeout

    def list_contacts(
        self, page_size: int = 10, person_fields: str = "names,emailAddresses"
    ):
        """Returns a list of contacts (read-only)."""
        parameters = {"pageSize": page_size, "personFields": person_fields}
        encoded_params = parse.urlencode(parameters)
        url = f"{self.PEOPLE_API_URL}?{encoded_params}"

        req = request.Request(
            url, headers={"Authorization": f"Bearer {self.access_token}"}
        )

        try:
            with request.urlopen(req, timeout=self.request_timeout) as response:
                payload = json.load(response)
        except HTTPError as exc:
            logging.error("Error listing contacts from Google Contacts: %s", exc)
            raise
        except URLError as exc:
            logging.error("Unable to reach Google Contacts API: %s", exc)
            raise

        return payload.get("connections", [])
