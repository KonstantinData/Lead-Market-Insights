"""Validation helpers for workflow extraction and research payloads."""

from __future__ import annotations

import re
from typing import Any, Mapping, MutableMapping
from urllib.parse import urlparse

PLACEHOLDER_DOMAINS = {
    "example.com",
    "example.org",
    "example.net",
    "localhost",
}

PUBLIC_SUFFIX_RE = re.compile(r"^[a-z0-9.-]+\.[a-z]{2,}$")


class InvalidExtractionError(ValueError):
    """Raised when extraction results fail validation requirements."""


def normalize_domain(raw: str | None) -> str:
    """Normalise *raw* domain or URL to a lowercase domain string."""

    if not raw:
        return ""
    candidate = raw.strip().lower()
    if candidate.startswith(("http://", "https://")):
        candidate = urlparse(candidate).netloc
    if candidate.endswith("/"):
        candidate = candidate.rstrip("/")
    return candidate


def is_valid_business_domain(domain: str | None) -> bool:
    """Return ``True`` if *domain* appears to be a routable business domain."""

    candidate = normalize_domain(domain)
    if not candidate:
        return False
    if candidate in PLACEHOLDER_DOMAINS:
        return False
    if candidate.endswith((".local", ".lan")):
        return False
    if candidate.count(".") == 0:
        return False
    return bool(PUBLIC_SUFFIX_RE.match(candidate))


def validate_extraction_or_raise(info: Mapping[str, Any]) -> Mapping[str, Any]:
    """Validate ``info`` extracted for research and CRM dispatch."""

    company_name = (info.get("company_name") or info.get("name") or "").strip()
    domain = info.get("company_domain") or info.get("web_domain") or info.get("domain")
    normalised_domain = normalize_domain(domain)

    if not company_name:
        raise InvalidExtractionError("company_name missing")

    if not is_valid_business_domain(normalised_domain):
        raise InvalidExtractionError(f"invalid web_domain: {normalised_domain or domain!r}")

    payload = dict(info)
    payload["company_name"] = company_name
    payload["company_domain"] = normalised_domain
    payload["web_domain"] = normalised_domain
    return payload


def normalize_similar_companies(payload: MutableMapping[str, Any]) -> MutableMapping[str, Any]:
    """Ensure similar company payload contains semantic status metadata."""

    results = list(payload.get("results") or [])
    payload["results"] = results
    payload["result_count"] = len(results)
    payload["status"] = "no_candidates" if not results else payload.get("status", "completed")
    return payload


def finalize_dossier(payload: MutableMapping[str, Any]) -> MutableMapping[str, Any]:
    """Set dossier payload status based on available context."""

    summary = payload.get("summary")
    sources = payload.get("sources")
    has_context = bool(summary) or bool(sources)
    payload["status"] = payload.get("status", "completed") if has_context else "insufficient_context"
    return payload
