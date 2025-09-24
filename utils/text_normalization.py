"""Utility helpers for normalising free-form text input."""

from __future__ import annotations

import unicodedata


def normalize_text(value: object) -> str:
    """Return a consistently normalised representation of *value*.

    The function converts the input to ``str`` (treating ``None`` as an empty
    string), removes diacritics via Unicode NFKD decomposition, applies NFKC
    normalisation, strips leading/trailing whitespace and lower-cases the
    result.  The outcome is optimised for reliable trigger-word matching and
    can be safely reused in other text processing pipelines.
    """

    if value is None:
        raw_text = ""
    else:
        raw_text = str(value)

    decomposed = unicodedata.normalize("NFKD", raw_text)
    without_diacritics = "".join(
        character for character in decomposed if not unicodedata.combining(character)
    )
    normalised = unicodedata.normalize("NFKC", without_diacritics)
    return normalised.strip().lower()
