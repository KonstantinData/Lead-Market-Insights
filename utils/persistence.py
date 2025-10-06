"""Utilities for reliable JSON persistence."""

from __future__ import annotations

import json
import os
import tempfile
from copy import deepcopy
from pathlib import Path
from typing import Any, Callable, Tuple, Type

from pydantic import BaseModel, ConfigDict, Field


class ProcessedEventEntry(BaseModel):
    fingerprint: str
    updated: str | None = None

    model_config = ConfigDict(extra="allow")


class ProcessedEventsState(BaseModel):
    entries: dict[str, ProcessedEventEntry] = Field(default_factory=dict)

    model_config = ConfigDict(extra="allow")


class NegativeCacheEntry(BaseModel):
    fingerprint: str
    updated: str | None = None
    rule_hash: str | None = None
    decision: str | None = None
    first_seen: float | None = None
    last_seen: float | None = None
    classification_version: str | None = None

    model_config = ConfigDict(extra="allow")


class NegativeCacheState(BaseModel):
    version: int = Field(default=1)
    entries: dict[str, NegativeCacheEntry] = Field(default_factory=dict)

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


def _default_payload(default: Any) -> Any:
    if isinstance(default, (dict, list)):
        return deepcopy(default)
    if callable(default):  # type: ignore[callable-compat]
        result = default()
        return deepcopy(result)
    return deepcopy(default)


def load_json_or_default(
    path: str | os.PathLike[str],
    *,
    default: Any,
    model: Type[BaseModel] | None = None,
) -> Tuple[Any, str | None]:
    """Return validated JSON payload or a default schema.

    Parameters
    ----------
    path:
        Location of the JSON document to load.
    default:
        Either a JSON-serialisable object or a callable returning such an
        object. When validation fails or the file is missing/corrupt the
        default payload is returned. The callable form is evaluated each
        time to avoid shared references.
    model:
        Optional :class:`pydantic.BaseModel` used to validate and normalise
        the payload. When provided, a validation error results in falling
        back to the default payload which is persisted atomically.

    Returns
    -------
    tuple
        A ``(payload, reason)`` tuple. ``reason`` is ``None`` for successful
        loads, ``"missing"`` when the file was absent, and descriptive
        strings (``"invalid_json"``/``"validation_error"``/``"type_mismatch"``)
        when the persisted data was replaced by the default schema.
    """

    target = Path(path)
    fallback = _default_payload(default)

    if not target.exists():
        return fallback, "missing"

    try:
        raw = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        atomic_write_json(target, fallback, model=model)
        return fallback, "invalid_json"

    expected_type: Callable[[Any], bool] | None = None
    if isinstance(fallback, dict):
        expected_type = lambda payload: isinstance(payload, dict)
    elif isinstance(fallback, list):
        expected_type = lambda payload: isinstance(payload, list)

    if expected_type and not expected_type(raw):
        atomic_write_json(target, fallback, model=model)
        return fallback, "type_mismatch"

    try:
        if model is not None:
            if isinstance(raw, list):
                payload = [_validate_model(model, item) for item in raw]
            else:
                payload = _validate_model(model, raw)
        else:
            payload = raw
    except Exception:
        atomic_write_json(target, fallback, model=model)
        return fallback, "validation_error"

    return payload, None
