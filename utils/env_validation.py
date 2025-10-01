import os
import logging
from typing import List

LOG = logging.getLogger(__name__)


def _has_openai_key() -> bool:
    return bool(os.getenv("OPENAI_API_KEY") or os.getenv("OPEN_AI_KEY"))


REQUIRED = [
    "__OPENAI_KEY__",  # wird separat geprüft
    "HUBSPOT_ACCESS_TOKEN",
    "GOOGLE_CLIENT_ID",
    "GOOGLE_CLIENT_SECRET",
    "GOOGLE_REFRESH_TOKEN",
    "GOOGLE_CALENDAR_ID",
]


def validate_environment(strict: bool = True) -> bool:
    missing: List[str] = []
    for key in REQUIRED:
        if key == "__OPENAI_KEY__":
            if not _has_openai_key():
                missing.append("OPENAI_API_KEY (oder legacy OPEN_AI_KEY)")
            continue
        if not os.getenv(key):
            missing.append(key)

    if missing:
        LOG.error("Missing required environment variables: %s", ", ".join(missing))
        if strict:
            return False
    else:
        LOG.info("Environment validation passed.")
    return True
