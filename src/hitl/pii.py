"""Simple redaction helpers shared by the standalone HITL toolkit."""

from __future__ import annotations

import hashlib
import re
from typing import Any, Dict

from .contracts import MaskedPayload
from .logging_setup import get_logger


log = get_logger("hitl.pii", "pii.log")

EMAIL = re.compile(r"([A-Za-z0-9_.+-]+)@([A-Za-z0-9-]+\.[A-Za-z0-9-.]+)")
PHONE = re.compile(r"\+?\d[\d\s().-]{6,}\d")


def _hash(value: str) -> str:
    """Return a short deterministic token for the supplied *value*."""

    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:10]


def mask_pii(run_id: str, data: Dict[str, Any]) -> MaskedPayload:
    """Redact emails and phone numbers and record the masking metadata."""

    text = str(data)

    def _email_sub(match: re.Match[str]) -> str:
        local, domain = match.group(1), match.group(2)
        return f"***+{_hash(local)}@{domain}"

    def _phone_sub(match: re.Match[str]) -> str:
        return f"+***-{_hash(match.group(0))}"

    redacted = EMAIL.sub(_email_sub, text)
    redacted = PHONE.sub(_phone_sub, redacted)

    masked = MaskedPayload(
        run_id=run_id,
        data={"redacted": redacted},
        pii_redaction="v1",
    )
    log.info("pii_masked", extra={"run_id": run_id})
    return masked