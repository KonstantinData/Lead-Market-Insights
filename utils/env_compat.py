"""
Environment compatibility layer.

Ermöglicht weiterhin die Nutzung von OPEN_AI_KEY (legacy),
während moderner Code OPENAI_API_KEY erwartet.
Optional wird auch zurück-gefüllt.
"""

from __future__ import annotations
import os
import logging

_LOG = logging.getLogger(__name__)


def apply_env_compat(
    promote_legacy: bool = True,
    backfill_legacy: bool = True,
) -> None:
    legacy = os.getenv("OPEN_AI_KEY")
    canonical = os.getenv("OPENAI_API_KEY")

    if promote_legacy and not canonical and legacy:
        os.environ["OPENAI_API_KEY"] = legacy
        _LOG.debug("EnvCompat: promoted OPEN_AI_KEY -> OPENAI_API_KEY")

    if backfill_legacy and not legacy and canonical:
        os.environ["OPEN_AI_KEY"] = canonical
        _LOG.debug("EnvCompat: backfilled OPENAI_API_KEY -> OPEN_AI_KEY")
