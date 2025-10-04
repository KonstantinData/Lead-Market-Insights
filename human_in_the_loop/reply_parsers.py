"""Light-weight parsers for human-in-the-loop inbox replies."""

from __future__ import annotations

import re
from typing import Any, Dict


def _normalise_key(key: str) -> str:
    cleaned = re.sub(r"[^a-z0-9]+", "_", key.strip().lower())
    return cleaned.strip("_")


def parse_missing_info_reply(subject: str, body: str) -> Dict[str, Any]:
    """Return structured data extracted from a missing-info reply."""

    fields: Dict[str, str] = {}
    for line in body.splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        normalised_key = _normalise_key(key)
        if not normalised_key:
            continue
        cleaned_value = value.strip()
        if cleaned_value:
            fields[normalised_key] = cleaned_value

    outcome = "parsed" if fields else "received"
    return {"fields": fields, "outcome": outcome}


def parse_dossier_reply(subject: str, body: str) -> Dict[str, Any]:
    """Parse organiser dossier decisions from free-form replies."""

    text = f"{subject}\n{body}".lower()
    decision = None
    if re.search(r"\b(approve|approved|yes|yep|sure)\b", text):
        decision = "approved"
    elif re.search(r"\b(decline|declined|no|nope|reject|rejected)\b", text):
        decision = "declined"

    outcome = decision or "received"
    return {"decision": decision, "outcome": outcome}


__all__ = ["parse_missing_info_reply", "parse_dossier_reply"]
