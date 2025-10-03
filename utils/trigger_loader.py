"""Helpers for loading and normalising trigger word configuration."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable, List, Optional
import logging

from utils.text_normalization import normalize_text


def _deduplicate(words: Iterable[str]) -> List[str]:
    """Return a list with duplicates removed while preserving order."""

    seen = set()
    unique_words: List[str] = []
    for word in words:
        if word not in seen:
            seen.add(word)
            unique_words.append(word)
    return unique_words


def _prepare_words(raw_words: Iterable[str]) -> List[str]:
    """Normalise and clean raw trigger words."""

    normalised = [normalize_text(word) for word in raw_words]
    non_empty = [word for word in normalised if word]
    return _deduplicate(non_empty)


def load_trigger_words(
    env_value: Optional[str],
    *,
    triggers_file: Optional[Path] = None,
    logger: Optional[logging.Logger] = None,
) -> List[str]:
    """Load trigger words from the environment and an optional fallback file."""

    collected: List[str] = []

    if env_value:
        env_words = [
            segment.strip() for segment in env_value.split(",") if segment.strip()
        ]
        collected.extend(env_words)
        if logger is not None:
            logger.info(
                "Loaded %d trigger words from TRIGGER_WORDS environment variable.",
                len(env_words),
            )

    if not collected and triggers_file is not None:
        try:
            with triggers_file.open("r", encoding="utf-8") as handle:
                file_words = []
                for line in handle:
                    stripped = line.strip()
                    if not stripped or stripped.startswith("#"):
                        continue
                    file_words.append(stripped)
        except FileNotFoundError:
            if logger is not None:
                logger.warning("Trigger words file %s not found.", triggers_file)
        except OSError as exc:
            if logger is not None:
                logger.error(
                    "Unable to read trigger words file %s: %s", triggers_file, exc
                )
        else:
            collected.extend(file_words)
            if logger is not None:
                logger.info(
                    "Loaded %d trigger words from %s.", len(file_words), triggers_file
                )

    cleaned = _prepare_words(collected)

    if not cleaned and logger is not None:
        logger.info("No trigger words configured; falling back to agent defaults.")

    return cleaned
