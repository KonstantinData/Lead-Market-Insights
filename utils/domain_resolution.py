"""Company domain resolution helpers with mapping + heuristics."""

from __future__ import annotations

import logging
import re
from functools import lru_cache
from pathlib import Path
from typing import Any, Mapping, Optional, Tuple

try:  # pragma: no cover - dependency guard
    import yaml  # type: ignore
except ImportError:  # pragma: no cover - dependency guard
    yaml = None  # type: ignore

from utils.validation import is_valid_business_domain, normalize_domain

logger = logging.getLogger(__name__)

_DEFAULT_MAPPING_PATH = (
    Path(__file__).resolve().parent.parent / "config" / "company_domains.yaml"
)

_GENERIC_EMAIL_PROVIDERS = {
    "gmail.com",
    "googlemail.com",
    "yahoo.com",
    "yahoo.co.uk",
    "hotmail.com",
    "outlook.com",
    "live.com",
    "icloud.com",
    "me.com",
    "protonmail.com",
}

_HEURISTIC_TLDS = ("com", "io", "ai", "co")


def _normalise_company_key(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", name.strip().lower())


@lru_cache(maxsize=1)
def load_company_domain_mapping(
    path: Optional[str | Path] = None,
) -> dict[str, str]:
    """Return the curated mapping from company identifiers to domains."""

    target = Path(path) if path else _DEFAULT_MAPPING_PATH
    if yaml is None:
        logger.debug("PyYAML not installed; company domain mapping disabled")
        return {}
    if not target.exists():
        logger.debug("Company domain mapping file %s not found", target)
        return {}

    try:
        with target.open("r", encoding="utf-8") as handle:
            raw = yaml.safe_load(handle) or {}
    except Exception:
        logger.exception("Failed to load company domain mapping from %s", target)
        return {}

    mapping: dict[str, str] = {}
    if isinstance(raw, Mapping):
        for key, value in raw.items():
            if not isinstance(key, str) or not isinstance(value, str):
                continue
            slug = _normalise_company_key(key)
            domain = normalize_domain(value)
            if slug and is_valid_business_domain(domain):
                mapping[slug] = domain
    return mapping


def _extract_email_domain(value: Any) -> str | None:
    if not isinstance(value, str) or "@" not in value:
        return None
    candidate = normalize_domain(value.split("@", 1)[-1])
    if not candidate or candidate in _GENERIC_EMAIL_PROVIDERS:
        return None
    if is_valid_business_domain(candidate):
        return candidate
    return None


def _resolve_from_mapping(company_name: str | None) -> Tuple[str | None, str | None]:
    if not company_name:
        return None, None
    slug = _normalise_company_key(company_name)
    if not slug:
        return None, None
    mapping = load_company_domain_mapping()
    domain = mapping.get(slug)
    if domain:
        return domain, "mapping"
    return None, None


def _resolve_from_info(info: Mapping[str, Any]) -> Tuple[str | None, str | None]:
    for key, value in info.items():
        if isinstance(key, str) and "email" in key.lower():
            domain = _extract_email_domain(value)
            if domain:
                return domain, "info_email"
    return None, None


def _resolve_from_event(event: Optional[Mapping[str, Any]]) -> Tuple[str | None, str | None]:
    if not isinstance(event, Mapping):
        return None, None

    def _iter_contacts() -> list[Any]:
        contacts: list[Any] = []
        for field in ("organizer", "creator"):
            value = event.get(field)
            if value is not None:
                contacts.append(value)
        attendees = event.get("attendees")
        if isinstance(attendees, list):
            contacts.extend(attendees)
        return contacts

    for contact in _iter_contacts():
        if isinstance(contact, Mapping):
            domain = _extract_email_domain(contact.get("email"))
            if domain:
                return domain, "contact_email"
        else:
            domain = _extract_email_domain(contact)
            if domain:
                return domain, "contact_email"
    return None, None


def _resolve_from_name(company_name: str | None) -> Tuple[str | None, str | None]:
    if not company_name:
        return None, None
    slug = _normalise_company_key(company_name)
    if not slug or slug.isdigit():
        return None, None
    for tld in _HEURISTIC_TLDS:
        candidate = f"{slug}.{tld}"
        if is_valid_business_domain(candidate):
            return candidate, "heuristic"
    return None, None


def resolve_company_domain(
    info: Mapping[str, Any],
    event: Optional[Mapping[str, Any]] = None,
) -> Tuple[str | None, str | None]:
    """Return ``(domain, source)`` for company info using deterministic order."""

    existing = normalize_domain(
        info.get("company_domain")
        or info.get("web_domain")
        or info.get("domain")
    )
    if is_valid_business_domain(existing):
        return existing, "provided"

    company_name = (info.get("company_name") or info.get("name") or "").strip()
    domain, source = _resolve_from_mapping(company_name)
    if domain:
        return domain, source

    domain, source = _resolve_from_info(info)
    if domain:
        return domain, source

    domain, source = _resolve_from_event(event)
    if domain:
        return domain, source

    domain, source = _resolve_from_name(company_name)
    if domain:
        return domain, source

    return None, None
