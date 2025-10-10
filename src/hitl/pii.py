"""
Minimal PII masking utility for emails and phones.
"""
from __future__ import annotations
import re, hashlib
from typing import Dict, Any
from .contracts import MaskedPayload
from .logging_setup import get_logger


log = get_logger("hitl.pii", "pii.log")


EMAIL = re.compile(r"([A-Za-z0-9_.+-]+)@([A-Za-z0-9-]+\.[A-Za-z0-9-.]+)")
PHONE = re.compile(r"\+?\d[\d\s().-]{6,}\d")


# Explanation: SHA256 short token for pseudonymization


def _hash(value: str) -> str:
return hashlib.sha256(value.encode("utf-8")).hexdigest()[:10]


# Explanation: redact sensitive items and return MaskedPayload


def mask_pii(run_id: str, data: Dict[str, Any]) -> MaskedPayload:
text = str(data)


def _email_sub(m: re.Match) -> str:
local, domain = m.group(1), m.group(2)
return f"***+{_hash(local)}@{domain}"


def _phone_sub(m: re.Match) -> str:
return f"+***-{_hash(m.group(0))}"


redacted = EMAIL.sub(_email_sub, text)
redacted = PHONE.sub(_phone_sub, redacted)


masked = MaskedPayload(run_id=run_id, data={"redacted": redacted}, pii_redaction="v1")
log.info("pii_masked", extra={"run_id": run_id})
return masked