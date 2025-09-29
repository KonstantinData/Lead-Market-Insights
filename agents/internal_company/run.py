"""Stub implementation for internal company search lookups."""

from __future__ import annotations

from typing import Any, Dict, Mapping


def run(trigger: Mapping[str, Any]) -> Dict[str, Any]:
    """Return a deterministic stub payload for internal research lookups."""

    payload = dict(trigger.get("payload") or {})
    payload.setdefault("exists", False)
    payload.setdefault("last_report_date", None)
    return {
        "payload": payload,
        "neighbors": [],
    }
