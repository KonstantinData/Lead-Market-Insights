"""Utilities for reliable JSON persistence."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any, Type

from pydantic import BaseModel, ConfigDict, Field


class ProcessedEventEntry(BaseModel):
    fingerprint: str
    updated: str | None = None

    model_config = ConfigDict(extra="allow")


class ProcessedEventsState(BaseModel):
    entries: dict[str, ProcessedEventEntry] = Field(default_factory=dict)

    model_config = ConfigDict(extra="allow")


class RunsIndexEntry(BaseModel):
    run_id: str
    log_path: str
    recorded_at: str
    log_size_bytes: int | None = None
    audit_log_path: str | None = None
    audit_entry_count: int | None = None

    model_config = ConfigDict(extra="allow")


def _validate_model(model: Type[BaseModel], data: Any) -> Any:
    if isinstance(data, model):
        validated = data
    else:
        validate = getattr(model, "model_validate", None)
        if callable(validate):
            validated = validate(data)
        else:
            validated = model.parse_obj(data)
    dump = getattr(validated, "model_dump", None)
    if callable(dump):
        return dump(mode="json")
    return json.loads(validated.json())


def atomic_write_json(
    path: str | os.PathLike[str],
    data: Any,
    *,
    model: Type[BaseModel] | None = None,
) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)

    payload = data
    if model is not None:
        if isinstance(data, list):
            payload = [_validate_model(model, item) for item in data]
        else:
            payload = _validate_model(model, data)

    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", dir=target.parent, delete=False
    ) as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
        handle.flush()
        os.fsync(handle.fileno())
        temp_name = handle.name

    os.replace(temp_name, target)
