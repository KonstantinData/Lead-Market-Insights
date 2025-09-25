# Utility helpers

The `utils` package contains reusable helper functions that support multiple agents and
integrations.

## Modules

| File | Description |
|------|-------------|
| [`duplicate_checker.py`](duplicate_checker.py) | Provides a simple `DuplicateChecker` class for determining whether an event ID has already been processed. Intended to be extended with more advanced deduplication logic. |
| [`text_normalization.py`](text_normalization.py) | Offers Unicode-aware normalisation utilities that strip diacritics, collapse whitespace, and perform case folding with memoisation. |
| [`trigger_loader.py`](trigger_loader.py) | Loads trigger words from environment variables and fallback files, normalises them, and removes duplicates before they reach the trigger detection agent. |

These utilities are extensively covered by the automated tests in [`tests/`](../tests/README.md).
