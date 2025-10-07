from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional


def save_crm_match(
    base_dir: Path,
    run_id: str,
    event_id: Optional[str],
    crm_payload: Dict[str, Any],
) -> Path:
    """Persist a CRM payload to an event-scoped artifact."""

    out_dir = base_dir / run_id
    out_dir.mkdir(parents=True, exist_ok=True)

    safe_event = _sanitise_identifier(event_id)
    if not safe_event:
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%f")
        safe_run = _sanitise_identifier(run_id) or "run"
        safe_event = f"{safe_run}_{timestamp}"

    payload = {
        "run_id": run_id,
        "event_id": str(event_id) if event_id is not None else None,
        "crm_payload": crm_payload,
        "written_at": datetime.now(timezone.utc).isoformat(),
    }

    out_file = out_dir / f"crm_match_{safe_event}.json"
    _atomic_write_json(out_file, payload)
    return out_file


def _sanitise_identifier(value: Optional[str]) -> str:
    if value is None:
        return ""
    text = str(value)
    text = re.sub(r"[^0-9A-Za-z._-]", "_", text)
    return text.strip("._-")


def _atomic_write_json(path: Path, payload: Dict[str, Any]) -> None:
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    with tmp_path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
    tmp_path.replace(path)


__all__ = ["save_crm_match"]
