"""Agent responsible for checking events against configured trigger words."""

from __future__ import annotations

from typing import Iterable, Sequence

from utils.text_normalization import normalize_text

_DEFAULT_TRIGGER_WORDS: Sequence[str] = ("trigger word", "demo")


def _prepare_trigger_words(trigger_words: Iterable[str] | None) -> tuple[str, ...]:
    """Return a tuple of normalised trigger words with duplicates removed."""

    cleaned = []
    seen = set()

    if trigger_words:
        for word in trigger_words:
            normalised = normalize_text(word)
            if not normalised or normalised in seen:
                continue
            seen.add(normalised)
            cleaned.append(normalised)

    if not cleaned:
        for word in _DEFAULT_TRIGGER_WORDS:
            normalised = normalize_text(word)
            if normalised not in seen:
                seen.add(normalised)
                cleaned.append(normalised)

    return tuple(cleaned)


class TriggerDetectionAgent:
    """Simple keyword-based trigger detection implementation."""

    def __init__(self, trigger_words: Iterable[str] | None = None) -> None:
        self.trigger_words = _prepare_trigger_words(trigger_words)

    def check(self, event: dict) -> bool:
        """Return ``True`` when *event* contains one of the trigger words."""

        summary = normalize_text(event.get("summary", ""))
        return any(word in summary for word in self.trigger_words)
