"""
Environment compatibility layer.

Purpose:
- Allow legacy scripts that define only OPEN_AI_KEY to work with code that expects OPENAI_API_KEY.
- Optionally mirror the other direction for tooling that might only export OPENAI_API_KEY.

Call apply_env_compat() as early as possible after loading environment variables.
"""

from __future__ import annotations
import os
import logging

_LOG = logging.getLogger(__name__)


def apply_env_compat(
    promote_legacy: bool = True,
    backfill_legacy: bool = True,
) -> None:
    """
    promote_legacy:
        If True and OPENAI_API_KEY is absent but OPEN_AI_KEY is present,
        copy OPEN_AI_KEY -> OPENAI_API_KEY.
    backfill_legacy:
        If True and OPEN_AI_KEY is absent but OPENAI_API_KEY is present,
        copy OPENAI_API_KEY -> OPEN_AI_KEY (helps older external scripts).
    """
    legacy = os.getenv("OPEN_AI_KEY")
    canonical = os.getenv("OPENAI_API_KEY")

    if promote_legacy and not canonical and legacy:
        os.environ["OPENAI_API_KEY"] = legacy
        _LOG.debug("EnvCompat: promoted OPEN_AI_KEY -> OPENAI_API_KEY")

    if backfill_legacy and not legacy and canonical:
        os.environ["OPEN_AI_KEY"] = canonical
        _LOG.debug("EnvCompat: backfilled OPENAI_API_KEY -> OPEN_AI_KEY")
