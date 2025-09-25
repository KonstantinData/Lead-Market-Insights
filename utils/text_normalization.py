"""Utility helpers for normalising free-form text input."""

from __future__ import annotations

from functools import lru_cache
import unicodedata


@lru_cache(maxsize=1024)
def _normalize_cached(raw_text: str) -> str:
    """Normalise a ``str`` instance using a cached transformation."""

    decomposed = unicodedata.normalize("NFKD", raw_text)
    without_diacritics = "".join(
        character for character in decomposed if not unicodedata.combining(character)
    )
    normalised = unicodedata.normalize("NFKC", without_diacritics)
    return normalised.strip().casefold()


def normalize_text(value: object) -> str:
    """Return a consistently normalised representation of *value*.

    The function converts the input to ``str`` (treating ``None`` as an empty
    string), removes diacritics via Unicode NFKD decomposition, applies NFKC
    normalisation, strips leading/trailing whitespace and performs
    locale-independent case-folding. The computation is cached for repeated
    inputs to avoid redundant Unicode work when normalising trigger words or
    recurring event summaries/descriptions.
    """

    if value is None:
        raw_text = ""
    else:
        raw_text = str(value)

    return _normalize_cached(raw_text)
