"""Helpers for persisting CRM lookup artifacts for the internal research agent."""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional


@dataclass
class CrmMatchArtifact:
    """Serializable representation of a CRM match artifact."""

    run_id: str
    event_id: Optional[str]
    company_name: str
    company_domain: str
    crm_lookup: Dict[str, Any]
    written_at: str


def build_crm_match_payload(
    *,
    run_id: str,
    event_id: Optional[str],
    company_name: str,
    company_domain: str,
    crm_lookup: Dict[str, Any],
    timestamp: Optional[str] = None,
) -> Dict[str, Any]:
    """Create a JSON-serialisable payload for a CRM match artifact."""

    artifact = CrmMatchArtifact(
        run_id=run_id,
        event_id=str(event_id) if event_id is not None else None,
        company_name=company_name,
        company_domain=company_domain,
        crm_lookup=crm_lookup,
        written_at=timestamp or datetime.now(timezone.utc).isoformat(),
    )
    return asdict(artifact)


def persist_crm_match(
    artifact_root: Path,
    run_id: str,
    event_id: Optional[str],
    payload: Dict[str, Any],
) -> Path:
    """Persist the CRM match payload in an event-scoped JSON artifact."""

    run_dir = artifact_root / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    safe_event = _sanitise_identifier(event_id)
    if not safe_event:
        safe_event = f"{_sanitise_identifier(run_id) or 'run'}_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%f')}"

    out_file = run_dir / f"crm_match_{safe_event}.json"
    _atomic_write_json(out_file, payload)
    return out_file


def _sanitise_identifier(value: Optional[str]) -> str:
    if value is None:
        return ""
    text = str(value)
    text = re.sub(r"[^0-9A-Za-z._-]", "_", text)
    text = text.strip("._-")
    return text


def _atomic_write_json(path: Path, payload: Dict[str, Any]) -> None:
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    with tmp_path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
    tmp_path.replace(path)
