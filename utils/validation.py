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

LEGAL_SUFFIX_RE = re.compile(
    r"("  # common corporate suffixes, anchored at end with optional whitespace
    r"gmbh(?:\s*&\s*co\.?\s*kg)?|ag|ug|kg|ohg|e\.?k\.?|kgaa|se|"
    r"limited|ltd|inc|llc|llp|plc|"
    r"sarl|s\.?a\.?r\.?l\.?|sas|bv|nv|ab|oy|a/s|aps|"
    r"s\.?p\.?a\.?|spa|srl|"
    r"sp\.\s*z\s*o\.?o\.?|spzoo|"
    r"s\.?a\.?|sa"
    r")\s*$",
    re.IGNORECASE,
)

SALUTATION_HEAD_RE = re.compile(
    r"^\s*(herr|hr\.?|frau|fr\.?|firma|fa\.?|mr\.?|mrs\.?|ms\.?)\b",
    re.IGNORECASE,
)


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


def _squash_internal_whitespace(text: str) -> str:
    """Collapse repeated whitespace into single spaces and strip the result."""

    return re.sub(r"\s+", " ", text).strip()


def _starts_with_salutation(company_name: str) -> bool:
    """Return ``True`` when *company_name* begins with a salutation or generic marker."""

    return bool(SALUTATION_HEAD_RE.search(company_name))


def _has_legal_suffix(company_name: str) -> bool:
    """Return ``True`` if *company_name* ends with a recognised legal entity suffix."""

    return bool(LEGAL_SUFFIX_RE.search(company_name))


def _strip_leading_salutations(company_name: str) -> str:
    """Remove salutation tokens from the head of *company_name* and normalise spacing."""

    remainder = company_name
    while True:
        match = SALUTATION_HEAD_RE.match(remainder)
        if not match:
            break
        remainder = remainder[match.end() :]
        remainder = remainder.lstrip(" ,.-")
    return _squash_internal_whitespace(remainder)


def _extract_domain_keyword(domain: str) -> str:
    """Return a representative keyword for *domain* to match against company names."""

    labels = [label for label in domain.split(".") if label and label.lower() != "www"]
    if not labels:
        return ""
    return max(labels, key=len)


def validate_extraction_or_raise(info: Mapping[str, Any]) -> Mapping[str, Any]:
    """Validate ``info`` extracted for research and CRM dispatch."""

    company_name_raw = (info.get("company_name") or info.get("name") or "").strip()
    domain = info.get("company_domain") or info.get("web_domain") or info.get("domain")
    normalised_domain = normalize_domain(domain)

    if not company_name_raw:
        raise InvalidExtractionError("company_name missing")

    company_name = _squash_internal_whitespace(company_name_raw)

    if not normalised_domain:
        raise InvalidExtractionError("company_domain missing")

    if not is_valid_business_domain(normalised_domain):
        raise InvalidExtractionError(f"invalid web_domain: {normalised_domain or domain!r}")

    starts_with_salutation = _starts_with_salutation(company_name)
    has_legal_suffix = _has_legal_suffix(company_name)

    if starts_with_salutation and not has_legal_suffix:
        stripped = _strip_leading_salutations(company_name)
        domain_keyword = _extract_domain_keyword(normalised_domain)
        if (
            stripped
            and not _starts_with_salutation(stripped)
            and (
                _has_legal_suffix(stripped)
                or (
                    domain_keyword
                    and domain_keyword.lower() in stripped.lower()
                )
            )
        ):
            company_name = stripped
        else:
            raise InvalidExtractionError(
                "company_name starts with a salutation but lacks a legal entity suffix"
            )

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
