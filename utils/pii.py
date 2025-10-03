"""Utilities for masking personally identifiable information (PII)."""

from __future__ import annotations

import re
from typing import Any, Iterable, Mapping, Sequence, Set

_REDACTED_EMAIL = "<redacted-email>"
_REDACTED_PHONE = "<redacted-phone>"
_REDACTED_GENERIC = "<redacted>"
_REDACTED_NAME = "<redacted-name>"
_REDACTED_ADDRESS = "<redacted-address>"

_EMAIL_PATTERN = re.compile(
    r"(?P<local>[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+)@(?P<domain>[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+)"
)
_PHONE_PATTERN = re.compile(r"(?<!\w)(?:\+?\d[\d\s().-]{6,}\d)(?!\w)")
_LONG_NUMBER_PATTERN = re.compile(r"\b\d{4,}\b")

_DEFAULT_WHITELIST: Set[str] = {
    "company",
    "company_name",
    "companyname",
    "business",
    "business_name",
    "organisation",
    "organization",
    "org",
    "org_name",
    "web_domain",
    "domain",
    "website",
    "summary",
    "description",
    "id",
    "event_id",
}

_CONTAINER_KEYS = {
    "organizer",
    "organiser",
    "creator",
    "attendees",
    "participants",
    "contact",
    "contacts",
    "person",
    "people",
    "owner",
}


def _normalise(value: Any) -> str:
    return str(value).strip().lower()


def _categorise(key: str) -> str | None:
    mapping = {
        "email": _REDACTED_EMAIL,
        "phone": _REDACTED_PHONE,
        "mobile": _REDACTED_PHONE,
        "telephone": _REDACTED_PHONE,
        "name": _REDACTED_NAME,
        "address": _REDACTED_ADDRESS,
        "location": _REDACTED_ADDRESS,
        "contact": _REDACTED_GENERIC,
    }
    for token, marker in mapping.items():
        if token in key:
            return marker
    return None


def _mask_string(value: str, *, strict: bool) -> str:
    masked = _EMAIL_PATTERN.sub(_REDACTED_EMAIL, value)
    masked = _PHONE_PATTERN.sub(_REDACTED_PHONE, masked)
    if strict:
        masked = _LONG_NUMBER_PATTERN.sub(_REDACTED_GENERIC, masked)
    return masked


def mask_pii(
    payload: Any,
    *,
    whitelist: Iterable[str] | None = None,
    mode: str = "standard",
) -> Any:
    """Return ``payload`` with personally identifiable information redacted."""

    whitelist_set = {_normalise(item) for item in (whitelist or _DEFAULT_WHITELIST)}
    strict = mode.lower() == "strict"

    def _mask(
        value: Any, key_hint: str | None = None, forced_marker: str | None = None
    ) -> Any:
        key_norm = _normalise(key_hint) if key_hint is not None else None
        if key_norm and key_norm in whitelist_set:
            forced_marker = None

        if isinstance(value, Mapping):
            result = {}
            for key, sub_value in value.items():
                sub_key_norm = _normalise(key)
                next_forced = forced_marker
                if sub_key_norm in whitelist_set:
                    result[key] = _mask(sub_value, sub_key_norm, None)
                    continue
                category_marker = _categorise(sub_key_norm)
                if category_marker:
                    next_forced = category_marker
                if sub_key_norm in _CONTAINER_KEYS:
                    next_forced = next_forced or _REDACTED_GENERIC
                result[key] = _mask(sub_value, sub_key_norm, next_forced)
            return result

        if isinstance(value, Sequence) and not isinstance(
            value, (str, bytes, bytearray)
        ):
            return [_mask(item, key_hint, forced_marker) for item in value]

        if isinstance(value, set):
            return {_mask(item, key_hint, forced_marker) for item in value}

        if isinstance(value, str):
            masked = _mask_string(value, strict=strict)
            if forced_marker and (key_norm not in whitelist_set if key_norm else True):
                return forced_marker
            if key_norm and key_norm not in whitelist_set:
                category_marker = _categorise(key_norm)
                if category_marker:
                    return category_marker
            return masked

        if forced_marker and (key_norm not in whitelist_set if key_norm else True):
            return forced_marker

        if (
            strict
            and isinstance(value, (int, float))
            and key_norm
            and key_norm not in whitelist_set
        ):
            return _REDACTED_GENERIC

        return value

    return _mask(payload)


__all__ = ["mask_pii"]
