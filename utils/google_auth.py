"""Helpers for working with Google OAuth credentials in async workflows."""

from __future__ import annotations

from typing import Mapping

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials


def ensure_access_token(creds: Credentials) -> str:
    """Ensure the credentials hold a valid access token and return it."""

    if not creds.valid and creds.refresh_token:
        creds.refresh(Request())
    if not creds.token:
        raise RuntimeError("Unable to obtain Google access token")
    return creds.token


def auth_header(token: str) -> Mapping[str, str]:
    return {"Authorization": f"Bearer {token}"}
