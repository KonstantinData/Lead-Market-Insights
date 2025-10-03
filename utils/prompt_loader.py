"""Utilities for loading structured LLM prompt templates with version control."""

from __future__ import annotations

import json
import logging
import re
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Mapping, MutableMapping, Optional

from config.config import settings

logger = logging.getLogger(__name__)

try:  # pragma: no cover - optional dependency guard
    import yaml  # type: ignore
except Exception:  # pragma: no cover - optional dependency guard
    yaml = None  # type: ignore

_PROMPT_FILE_SUFFIXES = {".json", ".yaml", ".yml"}


class PromptLoaderError(RuntimeError):
    """Raised when a prompt template cannot be located or parsed."""


class PromptDefinition(Dict[str, Any]):
    """Container for prompt data with helper properties."""

    @property
    def version(self) -> str:
        return str(self.get("version", ""))

    @property
    def name(self) -> str:
        return str(self.get("name", ""))

    @property
    def metadata(self) -> Mapping[str, Any]:
        metadata = self.get("metadata", {})
        if not isinstance(metadata, Mapping):
            raise PromptLoaderError(
                f"Prompt '{self.name}' version '{self.version}' metadata must be a mapping."
            )
        return metadata


def _normalise_prompt_name(name: str) -> str:
    normalised = name.strip().lower()
    if not normalised:
        raise PromptLoaderError("Prompt name must be a non-empty string.")
    return normalised


@lru_cache(maxsize=None)
def _prompt_index(directory: Path) -> Mapping[str, Mapping[str, Path]]:
    index: Dict[str, Dict[str, Path]] = {}

    if not directory.exists():
        raise PromptLoaderError(f"Prompt directory '{directory}' does not exist.")

    for path in directory.rglob("*"):
        if not path.is_file():
            continue
        if path.suffix.lower() not in _PROMPT_FILE_SUFFIXES:
            continue

        data = _load_prompt_file(path)
        name = _normalise_prompt_name(str(data.get("name", path.stem)))
        version = str(data.get("version"))
        if not version:
            raise PromptLoaderError(
                f"Prompt file '{path}' does not specify a 'version' field."
            )

        index.setdefault(name, {})[version] = path

    if not index:
        raise PromptLoaderError(f"No prompt templates discovered in '{directory}'.")

    return index


def _load_prompt_file(path: Path) -> PromptDefinition:
    text = path.read_text(encoding="utf-8")
    suffix = path.suffix.lower()

    if suffix == ".json":
        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:  # pragma: no cover - defensive branch
            raise PromptLoaderError(
                f"Failed to parse JSON prompt '{path}': {exc}."
            ) from exc
    elif suffix in {".yaml", ".yml"}:
        if yaml is None:  # pragma: no cover - dependency guard
            raise PromptLoaderError(
                "PyYAML is required to read YAML prompt templates but is not installed."
            )
        try:
            data = yaml.safe_load(text) or {}
        except yaml.YAMLError as exc:  # pragma: no cover - defensive branch
            raise PromptLoaderError(
                f"Failed to parse YAML prompt '{path}': {exc}."
            ) from exc
    else:  # pragma: no cover - extension guard
        raise PromptLoaderError(f"Unsupported prompt file format: '{path.suffix}'.")

    if not isinstance(data, MutableMapping):
        raise PromptLoaderError(
            f"Prompt file '{path}' must contain a mapping at the top level."
        )

    return PromptDefinition(data)


def _version_sort_key(version: str) -> tuple:
    numeric_parts = [int(part) for part in re.findall(r"\d+", version)]
    prefix = re.split(r"\d", version, maxsplit=1)[0]
    return (prefix, numeric_parts, version)


def clear_prompt_cache() -> None:
    """Clear cached prompt indices, primarily for use in unit tests."""

    _prompt_index.cache_clear()


def get_prompt(name: str, version: Optional[str] = None) -> PromptDefinition:
    """Load a prompt definition based on configured or explicit version selection."""

    directory = settings.prompt_directory
    index = _prompt_index(directory)
    normalised_name = _normalise_prompt_name(name)

    if normalised_name not in index:
        available = ", ".join(sorted(index)) or "<none>"
        raise PromptLoaderError(
            f"Prompt '{name}' was not found. Available prompts: {available}."
        )

    prompt_versions = index[normalised_name]

    selected_version = version
    if selected_version is None:
        configured = settings.prompt_versions.get(normalised_name)
        if configured:
            selected_version = configured
    if selected_version is None:
        selected_version = _latest_version(prompt_versions)

    if selected_version not in prompt_versions:
        available_versions = ", ".join(sorted(prompt_versions))
        raise PromptLoaderError(
            f"Prompt '{name}' version '{selected_version}' was not found. "
            f"Available versions: {available_versions}."
        )

    path = prompt_versions[selected_version]
    prompt = _load_prompt_file(path)

    metadata = prompt.metadata
    for field in ("temperature", "max_tokens"):
        if field not in metadata:
            raise PromptLoaderError(
                f"Prompt '{prompt.name}' version '{prompt.version}' is missing metadata field '{field}'."
            )

    logger.info(
        "Loaded prompt '%s' version '%s' from %s (temperature=%s, max_tokens=%s)",
        prompt.name,
        prompt.version,
        path,
        metadata.get("temperature"),
        metadata.get("max_tokens"),
    )

    return prompt


def _latest_version(version_map: Mapping[str, Path]) -> str:
    return max(version_map, key=_version_sort_key)
